"""Deterministic extraction of entity references from a routed query (FR-03, AD-7, D6).

Extraction only finds the *tokens the operator typed*; resolving them against state (exact,
case-folded, never fuzzy) is the resolver's job. Nothing here guesses.
"""

from __future__ import annotations

import pytest

from src.domain.references import (
    AccessDenialReferences,
    extract_access_denial_references,
    extract_follow_up_reference,
)

pytestmark = pytest.mark.unit

CASES = [
    ("why was alex denied deepseek-coder", "alex", "deepseek-coder"),
    ("Why was student alex denied access to deepseek-coder?", "alex", "deepseek-coder"),
    ("WHY WAS ALEX DENIED DEEPSEEK-CODER", "ALEX", "DEEPSEEK-CODER"),  # case is preserved
    ("  why   was\talex   denied   deepseek-coder  ", "alex", "deepseek-coder"),
    ("why was alex blocked from deepseek-coder", "alex", "deepseek-coder"),
    ("why was alex refused deepseek-coder", "alex", "deepseek-coder"),
    ("why can't alex access deepseek-coder", "alex", "deepseek-coder"),
    ("why can’t alex access deepseek-coder", "alex", "deepseek-coder"),
    ("why cannot alex access deepseek-coder?", "alex", "deepseek-coder"),
    ("why is alex not allowed to access deepseek-coder", "alex", "deepseek-coder"),
    ("why is alex unable to access deepseek-coder", "alex", "deepseek-coder"),
    ("alex was denied access to deepseek-coder", "alex", "deepseek-coder"),
    ("why was mateo denied access to qwen-2.5-coder-7b", "mateo", "qwen-2.5-coder-7b"),
    ("why was ghost_user_99 denied deepseek-coder", "ghost_user_99", "deepseek-coder"),
    ("why was alex denied imaginary-model.", "alex", "imaginary-model"),  # trailing dot stripped
    ("why was the student alex denied the model deepseek-coder", "alex", "deepseek-coder"),
    ("why was user#alex denied model#deepseek-coder", "user#alex", "model#deepseek-coder"),
]


@pytest.mark.parametrize(("query", "user", "model"), CASES)
def test_the_user_and_model_tokens_are_extracted_as_typed(
    query: str, user: str, model: str
) -> None:
    assert extract_access_denial_references(query) == AccessDenialReferences(user, model)


@pytest.mark.parametrize(
    "query",
    [
        "why was alex denied",
        "why was alex denied?",
        "denied",
        "what's the weather?",
        "why is the sky blue",
        "",
        "   ",
    ],
)
def test_a_query_that_names_no_user_and_model_yields_nothing(query: str) -> None:
    assert extract_access_denial_references(query) is None


def test_extraction_never_invents_a_token_that_is_not_in_the_text() -> None:
    query = "why was alex denied deepseek-coder"
    found = extract_access_denial_references(query)
    assert found is not None
    for token in (found.user, found.model):
        assert token in query


@pytest.mark.parametrize(
    ("query", "ref"),
    [
        ("and what about mateo?", "mateo"),
        ("what about mateo", "mateo"),
        ("How about Mateo?", "Mateo"),
        ("also what about ws-gpu-12.", "ws-gpu-12"),
        ("then how about user#mateo?", "user#mateo"),
    ],
)
def test_a_follow_up_names_exactly_one_reference(query: str, ref: str) -> None:
    assert extract_follow_up_reference(query) == ref


@pytest.mark.parametrize(
    "query", ["why was alex denied deepseek-coder", "what about", "tell me about mateo", ""]
)
def test_text_that_is_not_a_follow_up_has_no_follow_up_reference(query: str) -> None:
    assert extract_follow_up_reference(query) is None
