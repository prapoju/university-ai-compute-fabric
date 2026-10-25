"""Generic read-only record store: the extension seam for new entity types (NFR-10).

A new entity type is one fixture set, one query-only port and one adapter wrapping a
``RecordStore``. The store owns the shared read rules from contracts.md section 3 - id
validation (P-port-1), case-folded exact matching, stable ordering, capped pagination - and
hands out deep copies so a caller can never corrupt the estate it reads from.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable
from typing import Generic, TypeVar

from src.domain.result import Failure, Ok, Result

T = TypeVar("T")

MAX_ID_LENGTH = 200
MAX_PAGE_SIZE = 100  # D46


class RecordStore(Generic[T]):  # noqa: UP046 - explicit TypeVar keeps the seam readable
    def __init__(self, records: Iterable[T], id_of: Callable[[T], str]) -> None:
        self._id_of = id_of
        self._records: tuple[T, ...] = tuple(sorted(records, key=id_of))
        self._index = {id_of(record).casefold(): record for record in self._records}
        if len(self._index) != len(self._records):
            raise ValueError("duplicate ids (compared case-folded) in RecordStore")

    def __len__(self) -> int:
        return len(self._records)

    def get(self, key: str) -> Result[T | None]:
        """Exact, case-folded lookup by full key (``user#alex``); a miss is ``Ok(None)``."""
        if (problem := check_id(key)) is not None:
            return problem
        found = self._index.get(key.casefold())
        return Ok(None if found is None else copy.deepcopy(found))

    def browse(self, q: str, page: int, page_size: int) -> Result[list[T]]:
        """Case-folded exact match on the full key or its bare id; empty ``q`` lists all."""
        if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
            observed = (f"page={page}, page_size={page_size}; page>=1 and 1<=page_size<=100",)
            return Failure("PAGINATION_INVALID", observed=observed)
        needle = q.strip().casefold()
        matching = [r for r in self._records if not needle or self._matches(r, needle)]
        window = matching[(page - 1) * page_size : page * page_size]
        return Ok(copy.deepcopy(window))

    def all(self) -> list[T]:
        """Every record in id order, as copies (used by ``select`` and snapshots)."""
        return copy.deepcopy(list(self._records))

    def _matches(self, record: T, needle: str) -> bool:
        key = self._id_of(record).casefold()
        return needle == key or needle == key.partition("#")[2]


def check_id(key: str) -> Failure | None:
    """P-port-1: ``id`` is non-empty and at most 200 characters."""
    if not 1 <= len(key) <= MAX_ID_LENGTH:
        observed = (f"id length must be 1..{MAX_ID_LENGTH}; received {len(key)}",)
        return Failure("VALIDATION_MALFORMED_BODY", observed=observed)
    return None
