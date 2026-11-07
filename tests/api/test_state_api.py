"""Story 1.5 - the state inspection routes through the real composition root (AC 7, AC 8, FR-12)."""

from __future__ import annotations

import json
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import PROJECT_ROOT, Settings
from src.domain import canonical_strings as cs
from src.dto import BrowseStateResponse

pytestmark = pytest.mark.api

ESTATE = PROJECT_ROOT / "fixtures" / "estate"
STATE = "/api/v1/state"
# route name -> the fixture record's id field (§0.2)
ID_FIELDS = {
    "users": "id", "catalog": "id", "policy": "clause_id", "groups": "id", "jobs": "id",
    "nodes": "id", "reservations": "id", "windows": "window_id", "events": "event_id",
}  # fmt: skip


def fixture_records() -> list[tuple[str, str, dict]]:
    cases = []
    for route, field in ID_FIELDS.items():
        for record in json.loads((ESTATE / f"{route}.json").read_text(encoding="utf-8")):
            cases.append((route, record[field].partition("#")[2], record))
    return cases


ALL_RECORDS = fixture_records()


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False) as client:
        yield client


def test_the_sample_covers_every_record_of_every_fixture_file() -> None:
    assert {route for route, _, _ in ALL_RECORDS} == set(ID_FIELDS)
    assert len(ALL_RECORDS) == sum(
        len(json.loads((ESTATE / f"{r}.json").read_text("utf-8"))) for r in ID_FIELDS
    )


@pytest.mark.parametrize(("route", "bare", "record"), ALL_RECORDS, ids=lambda v: str(v)[:30])
def test_every_record_is_rendered_field_for_field(client, route, bare, record) -> None:
    response = client.get(f"{STATE}/{route}/{quote(bare, safe='')}")
    assert response.status_code == 200
    assert response.json() == record  # the bare record (D7), 100% of the sample


def test_an_absent_record_is_a_404_with_the_canonical_literal(client) -> None:
    response = client.get(f"{STATE}/nodes/ghost")
    assert response.status_code == 404
    body = response.json()
    assert (body["code"], body["message"]) == (
        "ENTITY_NOT_FOUND", cs.S_ENF.format(ref_list="node#ghost"),
    )  # fmt: skip
    assert body["message"] == "Entity Not Found in State: node#ghost."


def test_an_unknown_entity_type_is_a_400_on_both_routes(client) -> None:
    for path in (f"{STATE}/gpus/x", f"{STATE}/gpus"):
        response = client.get(path)
        assert response.status_code == 400
        assert response.json()["code"] == "VALIDATION_BAD_ENTITY_TYPE"


@pytest.mark.parametrize("bad", ["ws gpu 11", "a%2Fb", "x" * 201, "user%23alex"])
def test_a_malformed_id_is_a_400_not_a_framework_404(client, bad: str) -> None:
    response = client.get(f"{STATE}/nodes/{bad}")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_MALFORMED_BODY"


def test_browse_matches_the_bare_id_case_folded(client) -> None:
    response = client.get(f"{STATE}/nodes", params={"q": "WS-GPU-11"})
    assert response.status_code == 200
    body = BrowseStateResponse.model_validate(response.json())
    assert [item.id for item in body.items] == ["node#ws-gpu-11"] and body.total == 1


def test_browse_lists_everything_for_an_empty_q_with_the_full_total(client) -> None:
    body = client.get(f"{STATE}/nodes", params={"page_size": 10}).json()
    assert len(body["items"]) == 10 and body["total"] == 32
    assert (body["page"], body["page_size"]) == (1, 10)
    defaults = client.get(f"{STATE}/nodes").json()
    assert (defaults["page"], defaults["page_size"], len(defaults["items"])) == (1, 20, 20)


@pytest.mark.parametrize(("route", "expected"), [("windows", "window#night"), ("events", None)])
def test_windows_and_events_browse_too(client, route: str, expected) -> None:
    body = client.get(f"{STATE}/{route}").json()
    records = json.loads((ESTATE / f"{route}.json").read_text("utf-8"))
    by_id = sorted(records, key=lambda r: r[ID_FIELDS[route]])  # the stores keep id order
    assert body["items"] == by_id and body["total"] == len(records)
    if expected:
        one = client.get(f"{STATE}/{route}", params={"q": expected.upper()}).json()
        assert one["total"] == 1
    hit = client.get(f"{STATE}/events", params={"q": "evt-4711"}).json()
    assert [i["event_id"] for i in hit["items"]] == ["event#evt-4711"]


def test_a_page_beyond_total_is_empty_with_the_same_total(client) -> None:
    body = client.get(f"{STATE}/nodes", params={"page": 5, "page_size": 10}).json()
    assert body["items"] == [] and body["total"] == 32


@pytest.mark.parametrize(
    "params", [{"page_size": 101}, {"page": 10001, "page_size": 1}, {"page": 0}, {"page_size": 0}]
)
def test_invalid_pagination_is_a_400(client, params) -> None:
    response = client.get(f"{STATE}/nodes", params=params)
    assert response.status_code == 400
    assert response.json()["code"] == "PAGINATION_INVALID"


def test_the_estate_is_unchanged_after_every_call(monkeypatch) -> None:
    from src import bootstrap

    captured: list = []
    real = bootstrap.SimProviders.from_fixtures

    def capture(*args, **kwargs):
        captured.append(real(*args, **kwargs))
        return captured[-1]

    monkeypatch.setattr(bootstrap.SimProviders, "from_fixtures", capture)
    app = create_app(Settings.from_env({}))
    providers = captured[0]
    before = providers.estate_snapshot()
    with TestClient(app) as client:
        for route, bare, _ in ALL_RECORDS:
            client.get(f"{STATE}/{route}/{quote(bare, safe='')}")
        for route in ID_FIELDS:
            client.get(f"{STATE}/{route}", params={"page_size": 100})
            client.get(f"{STATE}/{route}", params={"q": "alex"})
        client.get(f"{STATE}/nodes/ghost")
    assert providers.estate_snapshot() == before  # AD-1


def test_state_reads_write_no_audit_row(client) -> None:
    client.get(f"{STATE}/users/alex")
    client.get(f"{STATE}/users")
    with client.app.state.container.writer.read() as db:
        assert db.execute("SELECT count(*) FROM audit_records").fetchone() == (0,)  # D2
