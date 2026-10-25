"""Exact, case-folded entity resolution against the read-only ports (AD-7, FR-03)."""

from __future__ import annotations

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimCatalog, SimUsers
from src.adapters.outbound.sim.record_store import RecordStore
from src.application.entity_resolver import (
    Ambiguous,
    EntityResolver,
    MissingContext,
    Resolved,
    Unresolved,
)
from src.domain.result import Failure, is_ok
from src.dto import ModelCatalogEntryDTO, UserRecordDTO

pytestmark = pytest.mark.unit


def resolver(providers) -> EntityResolver:
    return EntityResolver(users=providers.users, catalog=providers.catalog)


def resolve(providers, user: str, model: str):
    result = resolver(providers).resolve_user_and_model(user, model)
    assert is_ok(result), result
    return result.value


def test_exact_tokens_resolve_to_one_record_each(providers) -> None:
    resolved = resolve(providers, "alex", "deepseek-coder")
    assert isinstance(resolved, Resolved)
    assert (resolved.user.id, resolved.model.id) == ("user#alex", "model#deepseek-coder")


@pytest.mark.parametrize(
    ("user", "model"),
    [("ALEX", "DEEPSEEK-CODER"), ("Alex", "Deepseek-Coder"), ("user#ALEX", "model#deepseek-CODER")],
)
def test_matching_is_case_folded(providers, user: str, model: str) -> None:
    resolved = resolve(providers, user, model)
    assert isinstance(resolved, Resolved) and resolved.user.id == "user#alex"


@pytest.mark.parametrize(
    ("user", "model", "missing"),
    [
        ("ale", "deepseek-coder", ["user#ale"]),  # a prefix is not a match
        ("alex", "deepseek-code", ["model#deepseek-code"]),  # neither is a truncation
        ("alexx", "deepseek-coder", ["user#alexx"]),
        ("al3x", "deepseek-c0der", ["user#al3x", "model#deepseek-c0der"]),  # nor a typo
        ("ghost_user_99", "deepseek-coder", ["user#ghost_user_99"]),
        ("alex", "imaginary-model", ["model#imaginary-model"]),
        ("ghost", "imaginary", ["user#ghost", "model#imaginary"]),  # input order: user, then model
    ],
)
def test_nothing_fuzzy_ever_resolves_and_every_miss_is_named_in_order(
    providers, user: str, model: str, missing: list[str]
) -> None:
    result = resolve(providers, user, model)
    assert isinstance(result, Unresolved) and list(result.refs) == missing


def test_a_typed_token_of_the_wrong_type_is_unresolved_and_named_as_typed(providers) -> None:
    result = resolve(providers, "model#deepseek-coder", "user#alex")
    assert isinstance(result, Unresolved)
    assert list(result.refs) == ["model#deepseek-coder", "user#alex"]


def test_an_oversized_token_is_unresolved_not_a_provider_failure(providers) -> None:
    result = resolve(providers, "x" * 300, "deepseek-coder")
    assert isinstance(result, Unresolved) and result.refs == (f"user#{'x' * 300}",)


def test_a_provider_failure_aborts_resolution_it_is_never_reported_as_not_found(
    fixtures_copy, providers_from
) -> None:
    (fixtures_copy / "estate" / "users.json").unlink()
    result = resolver(providers_from(fixtures_copy)).resolve_user_and_model(
        "alex", "deepseek-coder"
    )
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


# -- follow-ups: session context first, then the provider (FR-02, D35) -------------------------
CONTEXT = ["user#alex", "model#deepseek-coder"]


def follow_up(providers, ref: str, context=CONTEXT):
    result = resolver(providers).resolve_follow_up(ref, context)
    assert is_ok(result), result
    return result.value


def test_a_bare_user_ref_is_resolved_and_the_model_comes_from_the_session(providers) -> None:
    resolved = follow_up(providers, "mateo")
    assert isinstance(resolved, Resolved)
    assert (resolved.user.id, resolved.model.id) == ("user#mateo", "model#deepseek-coder")


def test_a_bare_model_ref_is_resolved_and_the_user_comes_from_the_session(providers) -> None:
    resolved = follow_up(providers, "qwen-2.5-coder-7b")
    assert isinstance(resolved, Resolved)
    assert (resolved.user.id, resolved.model.id) == ("user#alex", "model#qwen-2.5-coder-7b")


def test_the_most_recent_context_entity_of_the_other_type_is_used(providers) -> None:
    context = ["user#alex", "model#deepseek-coder", "user#sofia", "model#llama-3-8b-instruct"]
    resolved = follow_up(providers, "mateo", context)
    assert (resolved.user.id, resolved.model.id) == ("user#mateo", "model#llama-3-8b-instruct")


def test_a_ref_that_is_nothing_is_not_found_by_its_raw_text(providers) -> None:
    result = follow_up(providers, "ghost")
    assert isinstance(result, Unresolved) and result.refs == ("ghost",)


def test_without_a_context_entity_of_the_other_type_the_follow_up_cannot_proceed(providers) -> None:
    assert isinstance(follow_up(providers, "mateo", []), MissingContext)
    assert isinstance(follow_up(providers, "mateo", ["user#alex"]), MissingContext)


def test_a_context_entity_is_re_resolved_against_the_provider_before_use(providers) -> None:
    result = follow_up(providers, "mateo", ["model#removed-since", "user#alex"])
    assert isinstance(result, Unresolved) and result.refs == ("model#removed-since",)


def test_a_bare_ref_matching_both_a_user_and_a_model_is_ambiguous() -> None:
    users = SimUsers(
        RecordStore(
            [UserRecordDTO(id="user#dual", display_name="D", role="student")], lambda r: r.id
        )
    )
    models = SimCatalog(
        RecordStore(
            [ModelCatalogEntryDTO(id="model#dual", name="dual", allowed_roles=["student"])],
            lambda r: r.id,
        )
    )
    result = EntityResolver(users=users, catalog=models).resolve_follow_up("dual", CONTEXT)
    assert is_ok(result) and result.value == Ambiguous("dual")


def test_follow_up_provider_failures_propagate(fixtures_copy, providers_from) -> None:
    (fixtures_copy / "estate" / "catalog.json").unlink()
    result = resolver(providers_from(fixtures_copy)).resolve_follow_up("mateo", CONTEXT)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
