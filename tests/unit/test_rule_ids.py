"""Story 1.6 task 4.4: the rule id of a policy clause is read from its evidence snippet."""

from __future__ import annotations

import pytest

from src.domain.rule_ids import rule_of_clause

pytestmark = pytest.mark.unit

S1_SNIPPET = (
    "policy#catalog.4.2 (RULE-CAT-04) [not-in-allowlist]: deepseek-coder requires enrollment "
    "in CS-480; the student role is not on the allowlist, so a student without that course "
    "entitlement is denied."
)


def test_the_s1_clause_carries_rule_cat_04() -> None:
    assert rule_of_clause(S1_SNIPPET, "policy#catalog.4.2") == "RULE-CAT-04"


def test_the_rule_of_the_named_clause_is_returned_among_several() -> None:
    snippet = (
        "policy#catalog.4.1 (RULE-CAT-01) [ok]: x; "
        "policy#catalog.4.2 (RULE-CAT-04) [denied]: y"
    )
    assert rule_of_clause(snippet, "policy#catalog.4.2") == "RULE-CAT-04"
    assert rule_of_clause(snippet, "policy#catalog.4.1") == "RULE-CAT-01"


def test_a_clause_id_that_is_only_a_prefix_of_another_does_not_match() -> None:
    snippet = "policy#catalog.4.20 (RULE-CAT-20) [ok]: z"
    assert rule_of_clause(snippet, "policy#catalog.4.2") is None


def test_a_clause_without_a_rule_id_has_none() -> None:
    snippet = "policy#catalog.4.2 [denied]: no rule printed"
    assert rule_of_clause(snippet, "policy#catalog.4.2") is None


def test_a_clause_that_is_not_in_the_snippet_has_none() -> None:
    assert rule_of_clause(S1_SNIPPET, "policy#catalog.9.9") is None


@pytest.mark.parametrize("code", ["RULE-cat-04", "RULE-CAT-4", "RULE-CAT-004", "CAT-04"])
def test_a_malformed_rule_code_is_not_extracted(code: str) -> None:
    snippet = f"policy#catalog.4.2 ({code}) [denied]: x"
    assert rule_of_clause(snippet, "policy#catalog.4.2") is None
