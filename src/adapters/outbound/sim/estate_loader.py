"""Loads and validates the seeded estate from ``fixtures/`` (offline, read-only; C-5, AD-12).

The whole estate is validated once, up front: every record against its contract DTO
(``extra="forbid"``), unique ids, ``{type}#{id}`` key prefixes, referential integrity,
half-open ``start < end`` intervals (D66) and runbook template rules (D44). Any problem fails
the *entire* load with ``PROVIDER_UNAVAILABLE`` - the adapters never serve a partial estate.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.domain.instants import parse_instant
from src.domain.result import Failure, Ok, Result
from src.dto import (
    AccessPolicyClauseDTO,
    GroupRecordDTO,
    JobRecordDTO,
    ModelCatalogEntryDTO,
    NodeRecordDTO,
    OperationalEventDTO,
    PolicyWindowDTO,
    ReservationRecordDTO,
    RunbookTemplateDTO,
    UserRecordDTO,
)
from src.ports.outbound import PolicyContent

MAX_POLICY_TEXT = 2000


class _FixtureError(Exception):
    """Internal: a fixture problem; converted to a typed ``Failure`` at the boundary."""


@dataclass(frozen=True)
class Estate:
    """The immutable, validated operational estate."""

    users: tuple[UserRecordDTO, ...]
    catalog: tuple[ModelCatalogEntryDTO, ...]
    policy: tuple[AccessPolicyClauseDTO, ...]
    groups: tuple[GroupRecordDTO, ...]
    jobs: tuple[JobRecordDTO, ...]
    nodes: tuple[NodeRecordDTO, ...]
    reservations: tuple[ReservationRecordDTO, ...]
    windows: tuple[PolicyWindowDTO, ...]
    events: tuple[OperationalEventDTO, ...]
    policy_content: tuple[PolicyContent, ...]
    runbooks: tuple[RunbookTemplateDTO, ...]


# store file -> (DTO, id attribute, entity type that prefixes the id)
_STORES: dict[str, tuple[type[BaseModel], str, str]] = {
    "users": (UserRecordDTO, "id", "user"),
    "catalog": (ModelCatalogEntryDTO, "id", "model"),
    "policy": (AccessPolicyClauseDTO, "clause_id", "policy"),
    "groups": (GroupRecordDTO, "id", "group"),
    "jobs": (JobRecordDTO, "id", "job"),
    "nodes": (NodeRecordDTO, "id", "node"),
    "reservations": (ReservationRecordDTO, "id", "reservation"),
    "windows": (PolicyWindowDTO, "window_id", "window"),
    "events": (OperationalEventDTO, "event_id", "event"),
}


def load_estate(fixtures_dir: Path) -> Result[Estate]:
    """Load ``fixtures_dir``. Never raises: a bad fixture is ``Failure(PROVIDER_UNAVAILABLE)``."""
    try:
        return Ok(_load(fixtures_dir))
    except (_FixtureError, OSError, ValueError) as exc:  # ValueError covers JSON + pydantic
        return Failure("PROVIDER_UNAVAILABLE", observed=(f"{type(exc).__name__}: {exc}",))


def _load(fixtures_dir: Path) -> Estate:
    if not fixtures_dir.is_dir():
        raise _FixtureError(f"fixtures directory not found: {fixtures_dir}")

    stores: dict[str, tuple[Any, ...]] = {}
    for name, (dto, id_attr, entity_type) in _STORES.items():
        stores[name] = _load_store(
            fixtures_dir / "estate" / f"{name}.json", dto, id_attr, entity_type
        )

    estate = Estate(
        **stores,
        policy_content=_load_policy_content(fixtures_dir / "policy_content"),
        runbooks=_load_runbooks(fixtures_dir / "runbooks"),
    )
    _check_references(estate)
    return estate


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_store(
    path: Path, dto: type[BaseModel], id_attr: str, entity_type: str
) -> tuple[Any, ...]:
    rows = _read_json(path)
    if not isinstance(rows, list) or not rows:
        raise _FixtureError(f"{path.name} must be a non-empty JSON list")
    records = [dto.model_validate(row) for row in rows]
    ids = [getattr(r, id_attr) for r in records]
    for record_id in ids:
        if not record_id.startswith(f"{entity_type}#"):
            raise _FixtureError(f"{path.name}: id {record_id!r} must start with '{entity_type}#'")
    if len({i.casefold() for i in ids}) != len(ids):
        raise _FixtureError(f"{path.name}: duplicate ids")
    return tuple(sorted(records, key=lambda r: getattr(r, id_attr)))


def _load_policy_content(folder: Path) -> tuple[PolicyContent, ...]:
    items: list[PolicyContent] = []
    for path in sorted(folder.glob("*.json")):
        raw = _read_json(path)
        if set(raw) != {"source_id", "text", "version"}:
            raise _FixtureError(f"{path.name}: expected exactly source_id, text, version")
        if not 1 <= len(raw["text"]) <= MAX_POLICY_TEXT:
            raise _FixtureError(f"{path.name}: text length must be 1..{MAX_POLICY_TEXT}")
        items.append(PolicyContent(raw["source_id"], raw["text"], raw["version"]))
    if not items:
        raise _FixtureError(f"no policy content found in {folder}")
    if len({i.source_id.casefold() for i in items}) != len(items):
        raise _FixtureError("policy_content: duplicate source_id")
    return tuple(items)


def _load_runbooks(folder: Path) -> tuple[RunbookTemplateDTO, ...]:
    templates: list[RunbookTemplateDTO] = []
    for path in sorted(folder.glob("*.json")):
        template = RunbookTemplateDTO.model_validate(_read_json(path))  # steps >= 1 (D44)
        if template.physical_intervention and not template.approved_source:
            raise _FixtureError(f"{path.name}: RUNBOOK_TEMPLATE_UNSOURCED (physical, no source)")
        templates.append(template)
    if len({t.error_code for t in templates}) != len(templates):
        raise _FixtureError("runbooks: duplicate error_code")
    return tuple(templates)


def _check_references(estate: Estate) -> None:
    users = {u.id for u in estate.users}
    models = {m.id for m in estate.catalog}
    groups = {g.id for g in estate.groups}
    jobs = {j.id for j in estate.jobs}
    nodes = {n.id for n in estate.nodes}

    checks: list[tuple[str, Callable[[], bool]]] = [
        ("policy.model_id", lambda: all(c.model_id in models for c in estate.policy)),
        ("groups.members", lambda: all(m in users for g in estate.groups for m in g.members)),
        ("jobs.group_id", lambda: all(j.group_id in groups for j in estate.jobs)),
        ("reservations.node_id", lambda: all(r.node_id in nodes for r in estate.reservations)),
        (
            "events.entity_ref",
            lambda: all(e.entity_ref in users | jobs | nodes for e in estate.events),
        ),
    ]
    for label, holds in checks:
        if not holds():
            raise _FixtureError(f"dangling reference in {label}")

    for interval in (*estate.reservations, *estate.windows):
        if parse_instant(interval.start) >= parse_instant(interval.end):
            raise _FixtureError(f"{interval!r}: start must be before end (D66)")
