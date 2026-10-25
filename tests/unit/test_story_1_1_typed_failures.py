"""Story 1.1 - typed ok | failure, never raised or fabricated (Gherkin scenario 4, AD-12).

Scenario: Missing record and failing provider are typed, never raised or fabricated
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.adapters.outbound.sim.estate_loader import load_estate
from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.domain.result import Failure, Ok, is_failure, is_ok
from src.dto import SelectorDTO
from src.ports.outbound import EventWindow

pytestmark = pytest.mark.unit

WINDOW = EventWindow("2026-10-16T00:00:00.000Z", "2026-10-17T00:00:00.000Z")


def _rewrite(directory: Path, relative: str, mutate) -> None:
    path = directory / relative
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(mutate(data)), encoding="utf-8")


# -- a missing record is Ok(None) ---------------------------------------------------------------
def test_a_missing_record_is_ok_none_not_a_failure_or_an_exception(providers: SimProviders) -> None:
    assert providers.users.get("user#ghost") == Ok(None)
    assert providers.nodes.get("node#nope") == Ok(None)


# -- a broken estate: every kind of fixture problem becomes PROVIDER_UNAVAILABLE ---------------
BREAKERS = {
    "missing-store-file": lambda d: (d / "estate" / "nodes.json").unlink(),
    "invalid-json": lambda d: (d / "estate" / "users.json").write_text("{nope", encoding="utf-8"),
    "extra-field-in-a-record": lambda d: _rewrite(
        d, "estate/users.json", lambda rows: [{**rows[0], "email": "x@y.z"}, *rows[1:]]
    ),
    "duplicate-id": lambda d: _rewrite(d, "estate/users.json", lambda rows: rows + [rows[0]]),
    "reservation-end-before-start": lambda d: _rewrite(
        d,
        "estate/reservations.json",
        lambda rows: [{**rows[0], "end": rows[0]["start"]}, *rows[1:]],
    ),
    "wrong-entity-type-prefix": lambda d: _rewrite(
        d, "estate/nodes.json", lambda rows: [{**rows[0], "id": "user#oops"}, *rows[1:]]
    ),
    "dangling-reference": lambda d: _rewrite(
        d, "estate/jobs.json", lambda rows: [{**rows[0], "group_id": "group#ghost"}, *rows[1:]]
    ),
    "runbook-without-steps": lambda d: _rewrite(
        d, "runbooks/err-thermal-88.json", lambda t: {**t, "steps": []}
    ),
    "unsourced-physical-runbook": lambda d: _rewrite(
        d, "runbooks/err-thermal-88.json", lambda t: {**t, "approved_source": None}
    ),
    "oversized-policy-content": lambda d: _rewrite(
        d, "policy_content/night-policy.json", lambda c: {**c, "text": "x" * 2001}
    ),
    "policy-content-text-null": lambda d: _rewrite(
        d, "policy_content/night-policy.json", lambda c: {**c, "text": None}
    ),
    "policy-content-source-id-not-a-string": lambda d: _rewrite(
        d, "policy_content/night-policy.json", lambda c: {**c, "source_id": 5}
    ),
    "policy-content-root-is-a-number": lambda d: (
        d / "policy_content" / "night-policy.json"
    ).write_text("7", encoding="utf-8"),
    "policy-content-extra-field": lambda d: _rewrite(
        d, "policy_content/night-policy.json", lambda c: {**c, "author": "x"}
    ),
    "event-with-an-impossible-date": lambda d: _rewrite(
        d,
        "estate/events.json",
        lambda rows: [{**rows[0], "timestamp": "2026-02-30T00:00:00Z"}, *rows[1:]],
    ),
    "reservation-with-an-impossible-date": lambda d: _rewrite(
        d,
        "estate/reservations.json",
        lambda rows: [{**rows[0], "start": "2026-13-01T00:00:00Z"}, *rows[1:]],
    ),
    "window-with-an-impossible-date": lambda d: _rewrite(
        d,
        "estate/windows.json",
        lambda rows: [{**rows[0], "end": "2026-10-32T06:00:00Z"}, *rows[1:]],
    ),
    "job-created-at-impossible-date": lambda d: _rewrite(
        d,
        "estate/jobs.json",
        lambda rows: [{**rows[0], "created_at": "2026-04-31T00:00:00Z"}, *rows[1:]],
    ),
    "runbooks-folder-missing": lambda d: shutil.rmtree(d / "runbooks"),
    "runbooks-folder-empty": lambda d: [p.unlink() for p in (d / "runbooks").glob("*.json")],
}


@pytest.mark.parametrize("name", sorted(BREAKERS))
def test_any_fixture_problem_fails_the_whole_load_with_provider_unavailable(
    fixtures_copy: Path, name: str
) -> None:
    BREAKERS[name](fixtures_copy)
    result = load_estate(fixtures_copy)
    assert isinstance(result, Failure), name
    assert result.code == "PROVIDER_UNAVAILABLE"
    assert result.observed, "the failure must say what was wrong"


def test_a_missing_fixtures_directory_is_a_failure_not_a_crash(tmp_path: Path) -> None:
    result = load_estate(tmp_path / "absent")
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def _calls(p: SimProviders):
    selector = SelectorDTO(method="filter", params={"status": "pending"})
    return {
        "users.get": lambda: p.users.get("user#alex"),
        "users.browse": lambda: p.users.browse("", 1, 10),
        "users.by_ids": lambda: p.users.by_ids(["user#alex"]),
        "catalog.get": lambda: p.catalog.get("model#deepseek-coder"),
        "catalog.browse": lambda: p.catalog.browse("", 1, 10),
        "policy.get": lambda: p.policy.get("policy#catalog.4.2"),
        "policy.for_model": lambda: p.policy.for_model("model#deepseek-coder"),
        "policy.browse": lambda: p.policy.browse("", 1, 10),
        "groups.get": lambda: p.groups.get("group#group-4"),
        "groups.browse": lambda: p.groups.browse("", 1, 10),
        "jobs.get": lambda: p.jobs.get("job#job-8823"),
        "jobs.select": lambda: p.jobs.select(selector),
        "jobs.browse": lambda: p.jobs.browse("", 1, 10),
        "nodes.get": lambda: p.nodes.get("node#ws-gpu-11"),
        "nodes.select": lambda: p.nodes.select(selector),
        "nodes.browse": lambda: p.nodes.browse("", 1, 10),
        "reservations.get": lambda: p.reservations.get("reservation#res-001"),
        "reservations.browse": lambda: p.reservations.browse("", 1, 10),
        "windows.get": lambda: p.windows.get("window#night"),
        "windows.list": lambda: p.windows.list(),
        "event_store.query": lambda: p.event_store.query("user#alex", "access_denied", WINDOW),
        "policy_content.get": lambda: p.policy_content.get("policy#night.2"),
        "runbook_registry.get": lambda: p.runbook_registry.get("ERR_THERMAL_88"),
    }


def test_every_port_read_returns_the_load_failure_and_no_partial_data(
    fixtures_copy: Path, providers_from
) -> None:
    (fixtures_copy / "estate" / "nodes.json").unlink()  # one broken store poisons the estate
    broken = providers_from(fixtures_copy)
    for name, call in _calls(broken).items():
        result = call()
        assert is_failure(result), name
        assert result.code == "PROVIDER_UNAVAILABLE", name


def test_the_same_calls_succeed_on_a_healthy_estate(providers: SimProviders) -> None:
    for name, call in _calls(providers).items():
        assert is_ok(call()), name


# -- port preconditions are typed validation failures (contracts.md section 3 P-port-1) --------
@pytest.mark.parametrize("bad_id", ["", "x" * 201])
def test_empty_or_oversized_ids_are_malformed_body(providers: SimProviders, bad_id: str) -> None:
    for read in (providers.users.get, providers.nodes.get, providers.jobs.get):
        result = read(bad_id)
        assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"


@pytest.mark.parametrize(("page", "size"), [(0, 10), (1, 0), (1, 101), (-3, 10)])
def test_bad_pagination_is_pagination_invalid(
    providers: SimProviders, page: int, size: int
) -> None:
    result = providers.nodes.browse("", page, size)
    assert isinstance(result, Failure) and result.code == "PAGINATION_INVALID"


def test_users_by_ids_rejects_non_user_keys(providers: SimProviders) -> None:
    result = providers.users.by_ids(["user#alex", "node#ws-gpu-11"])
    assert isinstance(result, Failure) and result.code == "VALIDATION_BAD_ENTITY_TYPE"


def test_policy_for_an_unknown_model_is_entity_not_found(providers: SimProviders) -> None:
    result = providers.policy.for_model("model#imaginary")
    assert isinstance(result, Failure) and result.code == "ENTITY_NOT_FOUND"


def test_unknown_policy_content_source_is_entity_not_found(providers: SimProviders) -> None:
    result = providers.policy_content.get("policy#does-not-exist")
    assert isinstance(result, Failure) and result.code == "ENTITY_NOT_FOUND"


@pytest.mark.parametrize(
    "selector",
    [
        SelectorDTO(method="teleport", params={}),
        SelectorDTO(method="filter", params={"not_a_column": 1}),
    ],
)
def test_select_rejects_unknown_methods_and_unknown_fields(
    providers: SimProviders, selector
) -> None:
    result = providers.jobs.select(selector)
    assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"


@pytest.mark.parametrize(
    ("kind", "start", "end"),
    [
        ("exploded", "2026-10-16T00:00:00.000Z", "2026-10-17T00:00:00.000Z"),
        ("access_denied", "2026-10-17T00:00:00.000Z", "2026-10-16T00:00:00.000Z"),
        ("access_denied", "2026-10-16T00:00:00.000Z", "2026-10-16T00:00:00Z"),
        ("access_denied", "yesterday", "tomorrow"),
    ],
)
def test_event_query_rejects_unknown_type_and_empty_or_inverted_windows(
    providers: SimProviders, kind: str, start: str, end: str
) -> None:
    result = providers.event_store.query("user#alex", kind, EventWindow(start, end))
    assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"
