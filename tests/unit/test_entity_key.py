"""``{type}#{id}`` parsing and case-folded comparison (contracts.md section 0.1/0.2, D61)."""

from __future__ import annotations

import pytest

from src.domain.entity_key import EntityKey, key_matches, parse_entity_key
from src.domain.result import Failure, Ok

pytestmark = pytest.mark.unit


def test_parses_type_and_id() -> None:
    assert parse_entity_key("node#ws-gpu-11") == Ok(EntityKey("node", "ws-gpu-11"))
    assert str(EntityKey("policy", "catalog.4.2")) == "policy#catalog.4.2"


def test_splits_on_the_first_unescaped_hash_only() -> None:
    # D61: a literal '#' in operator text is written '\#' and is part of the id
    assert parse_entity_key(r"job#build\#42") == Ok(EntityKey("job", "build#42"))
    assert parse_entity_key("job#a#b") == Ok(EntityKey("job", "a#b"))


@pytest.mark.parametrize("raw", ["gpu#ws-gpu-11", "#x", "cluster#1", "NODES#x"])
def test_unknown_entity_type_is_a_bad_entity_type_failure(raw: str) -> None:
    result = parse_entity_key(raw)
    assert isinstance(result, Failure) and result.code == "VALIDATION_BAD_ENTITY_TYPE"


@pytest.mark.parametrize("raw", ["", "node", "node#", "node#" + "x" * 201])
def test_missing_separator_empty_or_oversized_id_is_malformed(raw: str) -> None:
    result = parse_entity_key(raw)
    assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"


def test_matching_is_case_folded_and_exact_never_fuzzy() -> None:
    assert key_matches(EntityKey("user", "Alex"), EntityKey("user", "alex"))
    assert not key_matches(EntityKey("user", "alex"), EntityKey("user", "alexa"))
    assert not key_matches(EntityKey("user", "alex"), EntityKey("group", "alex"))


def test_the_type_is_case_folded_but_the_id_keeps_its_case() -> None:
    # AD-7: canonicalise then compare case-folded; get() and by_ids() must agree on this
    assert parse_entity_key("NODE#WS-gpu-11") == Ok(EntityKey("node", "WS-gpu-11"))
    assert parse_entity_key("User#Alex") == Ok(EntityKey("user", "Alex"))
