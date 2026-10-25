"""The prose guard (AD-8): prose may connect facts but never carry them."""

from __future__ import annotations

import pytest

from src.domain.prose_guard import scan_prose

pytestmark = pytest.mark.unit

TOKENS = {
    "user#alex", "alex", "alex rivera", "student", "model#deepseek-coder", "deepseek-coder",
    "policy#catalog.4.2", "catalog.4.2", "rule-cat-04", "not-in-allowlist", "evt-4711",
    "2026-10-16", "13:42:10",
}  # fmt: skip


def test_connective_prose_without_facts_has_no_hits() -> None:
    prose = "Here is what I found. The details below come straight from the records I looked up."
    assert scan_prose(prose, TOKENS) == []


@pytest.mark.parametrize(
    ("prose", "hit"),
    [
        ("Alex was denied.", "alex"),
        ("The student role is the problem.", "student"),
        ("See user#alex for details.", "user#alex"),
        ("This is governed by policy#catalog.4.2.", "policy#catalog.4.2"),
        ("The class is not-in-allowlist.", "not-in-allowlist"),
        ("It happened on 2026-10-16.", "2026-10-16"),
        ("Rule RULE-CAT-04 applies.", "rule-cat-04"),
        ("deepseek-coder is restricted", "deepseek-coder"),
        ("Alex Rivera asked", "alex rivera"),
    ],
)
def test_any_evidence_token_is_found_case_folded(prose: str, hit: str) -> None:
    assert hit in scan_prose(prose, TOKENS)


def test_matching_is_by_whole_word_so_harmless_substrings_pass() -> None:
    # "alexander" and "students" are different words; only the exact token is a fact
    assert scan_prose("Alexander met some students.", TOKENS) == []


def test_unicode_lookalikes_do_not_hide_a_fact() -> None:
    assert "alex" in scan_prose("ＡＬＥＸ was refused", TOKENS)  # full-width ALEX


def test_hits_are_unique_and_sorted_for_stable_logging() -> None:
    assert scan_prose("alex alex student alex", TOKENS) == ["alex", "student"]


def test_an_empty_token_set_never_matches() -> None:
    assert scan_prose("anything at all", set()) == []


@pytest.mark.parametrize(
    "prose",
    [
        "a​lex was refused",  # zero-width space
        "al­ex was refused",  # soft hyphen
        "ale⁠x was refused",  # word joiner
        "﻿alex",  # byte-order mark
    ],
)
def test_invisible_characters_cannot_split_a_fact_token(prose: str) -> None:
    assert "alex" in scan_prose(prose, TOKENS)
