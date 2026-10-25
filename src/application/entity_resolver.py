"""Entity resolution (AD-7, FR-03): exact, case-folded, never fuzzy, never an LLM.

The intent fixes the type of each reference, so a bare token is canonicalised to ``{type}#{id}``
and looked up through the read-only provider ports. Every required reference must resolve to
exactly one record before a diagnosis may start; every miss is named, in input order. A provider
*failure* is never reported as "not found": it aborts the turn (AD-12).

Follow-ups resolve against the session context first, and each context entity is re-resolved
against the provider before it is used (D35).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.entity_key import parse_entity_key
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import GroupRecordDTO, ModelCatalogEntryDTO, UserRecordDTO
from src.ports.outbound import CatalogPort, GroupsPort, UsersPort


@dataclass(frozen=True)
class Resolved:
    user: UserRecordDTO
    model: ModelCatalogEntryDTO


@dataclass(frozen=True)
class Unresolved:
    refs: tuple[str, ...]  # every reference that did not resolve, in input order


@dataclass(frozen=True)
class Ambiguous:
    ref: str  # a bare reference that matches both a user and a model (contracts P3)


@dataclass(frozen=True)
class MissingContext:
    """A follow-up needs an entity of the other type that the session does not hold."""


Resolution = Resolved | Unresolved | Ambiguous | MissingContext


def _is_miss(result: Result) -> bool:
    """A lookup that failed on the *shape* of the id means "no such entity", not "provider down"."""
    return is_failure(result) and result.code.startswith("VALIDATION_")


def _key(entity_type: str, token: str) -> tuple[str | None, str]:
    """``(canonical key | None, name to report)``: ``None`` means the token cannot be that type."""
    if "#" not in token:
        key = f"{entity_type}#{token}"
        return key, key
    parsed = parse_entity_key(token)
    if is_failure(parsed) or parsed.value.type != entity_type:
        return None, token  # typed as something else: unresolved, named as typed
    return str(parsed.value), str(parsed.value)


@dataclass(frozen=True)
class ResolvedGroup:
    group: GroupRecordDTO


class EntityResolver:
    def __init__(
        self, *, users: UsersPort, catalog: CatalogPort, groups: GroupsPort | None = None
    ) -> None:
        self._users = users
        self._catalog = catalog
        self._groups = groups

    # -- "why can't <group> run their job" (story 3.1) -------------------------------------------
    def resolve_group(self, token: str) -> Result[ResolvedGroup | Unresolved]:
        """Exact, case-folded group lookup; a miss is named as typed, never guessed (AD-7)."""
        if self._groups is None:
            return Failure("PROVIDER_UNAVAILABLE", observed=("groups port is not wired",))
        key, name = _key("group", token)
        found = self._lookup(self._groups.get, key)
        if is_failure(found):
            return found
        if found.value is None:
            return Ok(Unresolved((name,)))
        return Ok(ResolvedGroup(found.value))

    # -- "why was <user> denied <model>" -------------------------------------------------------
    def resolve_user_and_model(self, user_token: str, model_token: str) -> Result[Resolution]:
        user_key, user_name = _key("user", user_token)
        model_key, model_name = _key("model", model_token)
        user = self._lookup(self._users.get, user_key)
        model = self._lookup(self._catalog.get, model_key)
        if is_failure(user):
            return user
        if is_failure(model):
            return model
        missing = tuple(
            name
            for name, record in ((user_name, user.value), (model_name, model.value))
            if record is None
        )
        if missing:
            return Ok(Unresolved(missing))
        return Ok(Resolved(user.value, model.value))

    # -- "and what about <ref>?" ---------------------------------------------------------------
    def resolve_follow_up(self, ref: str, context_entities: Sequence[str]) -> Result[Resolution]:
        user_key, _ = _key("user", ref)
        model_key, _ = _key("model", ref)
        user = self._lookup(self._users.get, user_key)
        model = self._lookup(self._catalog.get, model_key)
        if is_failure(user):
            return user
        if is_failure(model):
            return model
        if user.value is not None and model.value is not None:
            return Ok(Ambiguous(ref))
        if user.value is None and model.value is None:
            return Ok(Unresolved((ref,)))

        if user.value is not None:
            other = self._from_context("model", context_entities, self._catalog.get)
            if other is None:
                return Ok(MissingContext())
            if is_failure(other):
                return other
            if isinstance(other.value, Unresolved):
                return Ok(other.value)
            return Ok(Resolved(user.value, other.value))

        other = self._from_context("user", context_entities, self._users.get)
        if other is None:
            return Ok(MissingContext())
        if is_failure(other):
            return other
        if isinstance(other.value, Unresolved):
            return Ok(other.value)
        return Ok(Resolved(other.value, model.value))

    # -- helpers -------------------------------------------------------------------------------
    @staticmethod
    def _lookup(get, key: str | None) -> Result:
        """``Ok(record | None)``; a malformed id is a miss, a provider failure propagates."""
        if key is None:
            return Ok(None)
        result = get(key)
        return Ok(None) if _is_miss(result) else result

    def _from_context(self, entity_type: str, context: Sequence[str], get):
        """Re-resolve the newest ``entity_type`` entity of the session (``None`` if it has none)."""
        prefix = f"{entity_type}#"
        key = next((k for k in reversed(context) if k.startswith(prefix)), None)
        if key is None:
            return None
        found = self._lookup(get, key)
        if is_failure(found):
            return found
        return Ok(Unresolved((key,))) if found.value is None else found


__all__ = [
    "Ambiguous",
    "EntityResolver",
    "MissingContext",
    "Resolution",
    "Resolved",
    "ResolvedGroup",
    "Unresolved",
]
