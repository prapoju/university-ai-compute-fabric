"""Fixture-backed simulated providers: one read-only adapter per outbound port (OP-1..OP-12).

Every adapter reads the same immutable :class:`Estate`; none has a write path. If the estate
failed to load, every read returns that typed ``Failure`` - never an exception, never partial
data (AD-12). Reads return deep copies, so callers cannot mutate the estate (AD-1).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel

from src.adapters.outbound.sim.clock_adapter import SimClock
from src.adapters.outbound.sim.estate_loader import Estate, load_estate
from src.adapters.outbound.sim.record_store import RecordStore, check_id
from src.domain.entity_key import parse_entity_key
from src.domain.instants import parse_instant
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import (
    AccessPolicyClauseDTO,
    EventType,
    GroupRecordDTO,
    JobRecordDTO,
    ModelCatalogEntryDTO,
    NodeRecordDTO,
    OperationalEventDTO,
    PolicyWindowDTO,
    ReservationRecordDTO,
    RunbookTemplateDTO,
    SelectorDTO,
    UserRecordDTO,
)
from src.ports.outbound import (
    CatalogPort,
    ClockPort,
    EventStorePort,
    EventWindow,
    GroupsPort,
    JobsPort,
    NodesPort,
    PolicyContent,
    PolicyContentPort,
    PolicyPort,
    ReservationsPort,
    RunbookRegistryPort,
    UsersPort,
    WindowsPort,
)

SELECT_CAP = 10_000  # D50: operational-store row cap bounds every ``select``
SELECT_METHOD = "filter"  # Selector.method understood by the simulated providers
EVENT_TYPES = frozenset(get_args(EventType))

Backing = RecordStore[Any] | Failure


def _read(backing: Backing, fn: Callable[[RecordStore[Any]], Result[Any]]) -> Result[Any]:
    """Run ``fn`` on the store, or hand back the load failure untouched."""
    return backing if isinstance(backing, Failure) else fn(backing)


def _select(backing: Backing, selector: SelectorDTO) -> Result[list[Any]]:
    """Equality filter over record fields; ordered by id, bounded by ``SELECT_CAP``."""

    def run(store: RecordStore[Any]) -> Result[list[Any]]:
        if selector.method != SELECT_METHOD:
            observed = (f"unknown selector method {selector.method!r}; expected {SELECT_METHOD!r}",)
            return Failure("VALIDATION_MALFORMED_BODY", observed=observed)
        records = store.all()
        fields = type(records[0]).model_fields if records else {}
        unknown = sorted(set(selector.params) - set(fields))
        if unknown:
            return Failure("VALIDATION_MALFORMED_BODY", observed=(f"unknown fields: {unknown}",))
        wanted = selector.params
        # exact type match: Python's == would let True match 1 and 1.0 match 1
        matching = [
            r
            for r in records
            if all(type(getattr(r, k)) is type(v) and getattr(r, k) == v for k, v in wanted.items())
        ]
        return Ok(matching[:SELECT_CAP])

    return _read(backing, run)


class SimUsers(UsersPort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def get(self, id: str) -> Result[UserRecordDTO | None]:
        return _read(self._backing, lambda s: s.get(id))

    def browse(self, q: str, page: int, page_size: int) -> Result[list[UserRecordDTO]]:
        return _read(self._backing, lambda s: s.browse(q, page, page_size))

    def by_ids(self, ids: list[str]) -> Result[list[UserRecordDTO]]:
        canonical: list[str] = []  # unescaped, type-folded keys, de-duplicated in input order
        for key in ids:
            parsed = parse_entity_key(key)
            if is_failure(parsed):
                return parsed
            if parsed.value.type != "user":
                observed = (f"{key!r} is not a user key",)
                return Failure("VALIDATION_BAD_ENTITY_TYPE", observed=observed)
            wanted = str(parsed.value)
            if wanted.casefold() not in {c.casefold() for c in canonical}:
                canonical.append(wanted)

        def run(store: RecordStore[Any]) -> Result[list[UserRecordDTO]]:
            found: list[UserRecordDTO] = []
            for key in canonical:
                result = store.get(key)
                if is_failure(result):
                    return result
                if result.value is not None:
                    found.append(result.value)
            return Ok(found)

        return _read(self._backing, run)


class SimCatalog(CatalogPort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def get(self, model_id: str) -> Result[ModelCatalogEntryDTO | None]:
        return _read(self._backing, lambda s: s.get(model_id))

    def browse(self, q: str, page: int, page_size: int) -> Result[list[ModelCatalogEntryDTO]]:
        return _read(self._backing, lambda s: s.browse(q, page, page_size))


class SimPolicy(PolicyPort):
    def __init__(self, clauses: Backing, catalog: Backing) -> None:
        self._clauses = clauses
        self._catalog = catalog

    def get(self, clause_id: str) -> Result[AccessPolicyClauseDTO | None]:
        return _read(self._clauses, lambda s: s.get(clause_id))

    def for_model(self, model_id: str) -> Result[list[AccessPolicyClauseDTO]]:
        if (problem := check_id(model_id)) is not None:
            return problem
        known = _read(self._catalog, lambda s: s.get(model_id))
        if is_failure(known):
            return known
        if known.value is None:
            return Failure(
                "ENTITY_NOT_FOUND", observed=(f"model {model_id!r} is not in the catalog",)
            )

        def run(store: RecordStore[Any]) -> Result[list[AccessPolicyClauseDTO]]:
            wanted = model_id.casefold()
            clauses = [c for c in store.all() if c.model_id.casefold() == wanted]
            return Ok(sorted(clauses, key=lambda c: c.clause_id))

        return _read(self._clauses, run)

    def browse(self, q: str, page: int, page_size: int) -> Result[list[AccessPolicyClauseDTO]]:
        return _read(self._clauses, lambda s: s.browse(q, page, page_size))


class SimGroups(GroupsPort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def get(self, group_id: str) -> Result[GroupRecordDTO | None]:
        return _read(self._backing, lambda s: s.get(group_id))

    def browse(self, q: str, page: int, page_size: int) -> Result[list[GroupRecordDTO]]:
        return _read(self._backing, lambda s: s.browse(q, page, page_size))


class SimJobs(JobsPort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def get(self, job_id: str) -> Result[JobRecordDTO | None]:
        return _read(self._backing, lambda s: s.get(job_id))

    def select(self, selector: SelectorDTO) -> Result[list[JobRecordDTO]]:
        return _select(self._backing, selector)

    def browse(self, q: str, page: int, page_size: int) -> Result[list[JobRecordDTO]]:
        return _read(self._backing, lambda s: s.browse(q, page, page_size))


class SimNodes(NodesPort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def get(self, node_id: str) -> Result[NodeRecordDTO | None]:
        return _read(self._backing, lambda s: s.get(node_id))

    def select(self, selector: SelectorDTO) -> Result[list[NodeRecordDTO]]:
        return _select(self._backing, selector)

    def browse(self, q: str, page: int, page_size: int) -> Result[list[NodeRecordDTO]]:
        return _read(self._backing, lambda s: s.browse(q, page, page_size))


class SimReservations(ReservationsPort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def get(self, reservation_id: str) -> Result[ReservationRecordDTO | None]:
        return _read(self._backing, lambda s: s.get(reservation_id))

    def browse(self, q: str, page: int, page_size: int) -> Result[list[ReservationRecordDTO]]:
        return _read(self._backing, lambda s: s.browse(q, page, page_size))


class SimWindows(WindowsPort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def get(self, window_id: str) -> Result[PolicyWindowDTO | None]:
        return _read(self._backing, lambda s: s.get(window_id))

    def list(self) -> Result[list[PolicyWindowDTO]]:
        return _read(self._backing, lambda s: Ok(s.all()))


class SimEventStore(EventStorePort):
    def __init__(self, backing: Backing) -> None:
        self._backing = backing

    def query(
        self, entity_ref: str, type: str, window: EventWindow
    ) -> Result[list[OperationalEventDTO]]:
        if (problem := check_id(entity_ref)) is not None:
            return problem
        if type not in EVENT_TYPES:
            observed = (f"unknown event type {type!r}",)
            return Failure("VALIDATION_MALFORMED_BODY", observed=observed)
        try:
            start, end = parse_instant(window.start), parse_instant(window.end)
        except ValueError as exc:
            return Failure("VALIDATION_MALFORMED_BODY", observed=(str(exc),))
        if start >= end:
            observed = ("window must satisfy start < end (half-open)",)
            return Failure("VALIDATION_MALFORMED_BODY", observed=observed)

        def run(store: RecordStore[Any]) -> Result[list[OperationalEventDTO]]:
            wanted = entity_ref.casefold()
            hits = [
                e
                for e in store.all()
                if e.type == type
                and e.entity_ref.casefold() == wanted
                and start <= parse_instant(e.timestamp) < end
            ]
            hits.sort(key=lambda e: (parse_instant(e.timestamp), e.event_id))
            return Ok(hits)

        return _read(self._backing, run)


class SimPolicyContent(PolicyContentPort):
    def __init__(self, contents: tuple[PolicyContent, ...] | Failure) -> None:
        self._contents = contents

    def get(self, source_id: str) -> Result[PolicyContent]:
        if (problem := check_id(source_id)) is not None:
            return problem
        if isinstance(self._contents, Failure):
            return self._contents
        for content in self._contents:
            if content.source_id.casefold() == source_id.casefold():
                return Ok(copy.deepcopy(content))
        return Failure(
            "ENTITY_NOT_FOUND", observed=(f"policy content {source_id!r} is not curated",)
        )


class SimRunbookRegistry(RunbookRegistryPort):
    def __init__(self, templates: tuple[RunbookTemplateDTO, ...] | Failure) -> None:
        self._templates = templates

    def get(self, error_code: str) -> Result[RunbookTemplateDTO | None]:
        if (problem := check_id(error_code)) is not None:
            return problem
        if isinstance(self._templates, Failure):
            return self._templates
        for template in self._templates:
            if template.error_code == error_code:  # exact-code lookup (AD-9)
                return Ok(copy.deepcopy(template))
        return Ok(None)


@dataclass(frozen=True)
class SimProviders:
    """The complete simulated provider ring plus the estate behind it."""

    users: SimUsers
    catalog: SimCatalog
    policy: SimPolicy
    groups: SimGroups
    jobs: SimJobs
    nodes: SimNodes
    reservations: SimReservations
    windows: SimWindows
    event_store: SimEventStore
    policy_content: SimPolicyContent
    runbook_registry: SimRunbookRegistry
    clock: SimClock
    estate: Result[Estate]
    fixtures_dir: Path

    @classmethod
    def from_fixtures(cls, fixtures_dir: Path, clock_start: str) -> SimProviders:
        estate = load_estate(fixtures_dir)

        def store(attr: str, id_of: Callable[[Any], str]) -> Backing:
            if isinstance(estate, Failure):
                return estate
            return RecordStore(getattr(estate.value, attr), id_of)

        catalog = store("catalog", lambda r: r.id)
        return cls(
            users=SimUsers(store("users", lambda r: r.id)),
            catalog=SimCatalog(catalog),
            policy=SimPolicy(store("policy", lambda r: r.clause_id), catalog),
            groups=SimGroups(store("groups", lambda r: r.id)),
            jobs=SimJobs(store("jobs", lambda r: r.id)),
            nodes=SimNodes(store("nodes", lambda r: r.id)),
            reservations=SimReservations(store("reservations", lambda r: r.id)),
            windows=SimWindows(store("windows", lambda r: r.window_id)),
            event_store=SimEventStore(store("events", lambda r: r.event_id)),
            policy_content=SimPolicyContent(
                estate if isinstance(estate, Failure) else estate.value.policy_content
            ),
            runbook_registry=SimRunbookRegistry(
                estate if isinstance(estate, Failure) else estate.value.runbooks
            ),
            clock=SimClock(clock_start),
            estate=estate,
            fixtures_dir=fixtures_dir,
        )

    def as_ports(self) -> dict[type, object]:
        """Port interface -> adapter, for the composition root's registry."""
        return {
            UsersPort: self.users,
            CatalogPort: self.catalog,
            PolicyPort: self.policy,
            GroupsPort: self.groups,
            JobsPort: self.jobs,
            NodesPort: self.nodes,
            ReservationsPort: self.reservations,
            WindowsPort: self.windows,
            EventStorePort: self.event_store,
            ClockPort: self.clock,
            PolicyContentPort: self.policy_content,
            RunbookRegistryPort: self.runbook_registry,
        }

    def estate_snapshot(self) -> dict[str, Any]:
        """A plain-data view of the estate itself (not of any copy), for equality checks."""
        if isinstance(self.estate, Failure):
            return {"failure": self.estate.code, "observed": list(self.estate.observed)}
        snapshot: dict[str, Any] = {}
        for name, items in vars(self.estate.value).items():
            snapshot[name] = [
                i.model_dump() if isinstance(i, BaseModel) else vars(i).copy() for i in items
            ]
        return snapshot
