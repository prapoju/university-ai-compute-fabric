"""``get_state_record`` and ``browse_state`` (contracts.md section 2, FR-12, I22, E13, E49).

One table maps each route name to its entity type and to the ``get`` / ``browse`` of its provider
port; a new entity type adds one row (NFR-10). It is a different key space from the citation-type
map of ``EvidenceService``, so the two stay separate. Every check runs before any read, and
nothing is written: the estate is unchanged afterwards (AD-1). Session-less reads are not
audited (story 1.5 D2).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from src.domain.error_catalog import fail
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import BrowseStateResponse, RecordDTO
from src.ports.inbound import StateUseCases
from src.ports.outbound import (
    CatalogPort,
    EventStorePort,
    GroupsPort,
    JobsPort,
    NodesPort,
    PolicyPort,
    ReservationsPort,
    UsersPort,
    WindowsPort,
)

STATE_ROW_CAP = 10_000  # D50 / E49: the most rows a browse can address or count
MAX_PAGE_SIZE = 100
_COUNT_PAGE = 100
_ID = re.compile(r"^[A-Za-z0-9._-]{1,200}$")

Get = Callable[[str], Result[Any]]
Browse = Callable[[str, int, int], Result[list[Any]]]


class StateService(StateUseCases):
    def __init__(
        self,
        *,
        users: UsersPort,
        catalog: CatalogPort,
        policy: PolicyPort,
        groups: GroupsPort,
        jobs: JobsPort,
        nodes: NodesPort,
        reservations: ReservationsPort,
        windows: WindowsPort,
        event_store: EventStorePort,
    ) -> None:
        # route name (§0.2) -> (entity type, get, browse)
        self._types: dict[str, tuple[str, Get, Browse]] = {
            "users": ("user", users.get, users.browse),
            "catalog": ("model", catalog.get, catalog.browse),
            "policy": ("policy", policy.get, policy.browse),
            "groups": ("group", groups.get, groups.browse),
            "jobs": ("job", jobs.get, jobs.browse),
            "nodes": ("node", nodes.get, nodes.browse),
            "reservations": ("reservation", reservations.get, reservations.browse),
            "windows": ("window", windows.get, windows.browse),
            "events": ("event", event_store.get, event_store.browse),
        }

    def _entry(self, route_name: str) -> tuple[str, Get, Browse] | Failure:
        entry = self._types.get(route_name)
        if entry is None:
            return fail("VALIDATION_BAD_ENTITY_TYPE", value=route_name, enum=list(self._types))
        return entry

    # -- get_state_record ----------------------------------------------------------------------
    def get_state_record(self, entity_type: str, id: str) -> Result[RecordDTO]:
        entry = self._entry(entity_type)
        if isinstance(entry, Failure):
            return entry
        if not _ID.fullmatch(id):
            observed = (f"id must match {_ID.pattern}",)
            return fail("VALIDATION_MALFORMED_BODY", observed=observed, schema_id="EntityIdPath")
        kind, get, _ = entry
        key = f"{kind}#{id}"
        found = get(key)
        if is_failure(found):
            return found
        if found.value is None:
            return fail("ENTITY_NOT_FOUND", ref_list=key)
        return Ok(found.value)

    # -- browse_state --------------------------------------------------------------------------
    def browse_state(
        self, entity_type: str, q: str, page: int, page_size: int
    ) -> Result[BrowseStateResponse]:
        entry = self._entry(entity_type)
        if isinstance(entry, Failure):
            return entry
        if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE or page * page_size > STATE_ROW_CAP:
            observed = (
                f"page={page}, page_size={page_size}; page>=1, 1<=page_size<=100 and"
                f" page <= {STATE_ROW_CAP} / page_size",
            )
            return fail("PAGINATION_INVALID", observed=observed, v=page_size)
        _, _, browse = entry
        items = browse(q, page, page_size)
        if is_failure(items):
            return items
        total = self._total(browse, q)
        if is_failure(total):
            return total
        return Ok(
            BrowseStateResponse(
                items=items.value, page=page, page_size=page_size, total=total.value
            )
        )

    @staticmethod
    def _total(browse: Browse, q: str) -> Result[int]:
        """Matched count, by paging the port, clamped to the row cap (story 1.5 D9)."""
        total = 0
        for page in range(1, STATE_ROW_CAP // _COUNT_PAGE + 1):
            chunk = browse(q, page, _COUNT_PAGE)
            if is_failure(chunk):
                return chunk
            total += len(chunk.value)
            if len(chunk.value) < _COUNT_PAGE:
                break
        return Ok(min(total, STATE_ROW_CAP))
