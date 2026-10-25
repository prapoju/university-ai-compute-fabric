"""``{type}#{id}`` entity keys (contracts.md section 0.1 ``EntityKey`` / ``RawRef``, D61).

Groundwork for exact-match entity resolution (AD-7); the resolver itself arrives in a later
story. Comparison is case-folded and exact - there is deliberately no fuzzy matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from src.domain.result import Failure, Ok, Result
from src.dto import EntityType

ENTITY_TYPES = frozenset(get_args(EntityType))
MAX_ID_LENGTH = 200


@dataclass(frozen=True)
class EntityKey:
    type: str
    id: str

    def __str__(self) -> str:
        return f"{self.type}#{self.id}"


def _split_on_first_unescaped_hash(raw: str) -> tuple[str, str] | None:
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and raw[i + 1 : i + 2] == "#":
            i += 2
            continue
        if raw[i] == "#":
            return raw[:i], raw[i + 1 :]
        i += 1
    return None


def parse_entity_key(raw: str) -> Result[EntityKey]:
    """Parse ``{type}#{id}``; a literal ``#`` inside the id is written ``\\#`` (D61)."""
    parts = _split_on_first_unescaped_hash(raw)
    if parts is None:
        return Failure("VALIDATION_MALFORMED_BODY", observed=(f"no '#' separator in {raw!r}",))
    entity_type, entity_id = parts
    if entity_type not in ENTITY_TYPES:
        observed = (f"unknown entity type {entity_type!r}",)
        return Failure("VALIDATION_BAD_ENTITY_TYPE", observed=observed)
    entity_id = entity_id.replace("\\#", "#")
    if not 1 <= len(entity_id) <= MAX_ID_LENGTH:
        observed = (f"id length must be 1..{MAX_ID_LENGTH}",)
        return Failure("VALIDATION_MALFORMED_BODY", observed=observed)
    return Ok(EntityKey(entity_type, entity_id))


def key_matches(a: EntityKey, b: EntityKey) -> bool:
    """Exact, case-folded equality of two keys (AD-7)."""
    return a.type == b.type and a.id.casefold() == b.id.casefold()
