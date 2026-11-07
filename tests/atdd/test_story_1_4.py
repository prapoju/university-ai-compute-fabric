"""Story 1.4 ATDD - citation coverage and 3x evidence-level determinism on the real app.

Every run builds the real app through ``create_app(Settings.from_env(...))``: real composition
root, real fixtures, real SQLite, the simulated prose writer, and the simulated clock frozen at
the same start (it never moves unless a scenario advances it). Determinism uses a **fresh** app
per run, so the clock read ids and every other id restart identically (decision-log AD-21).
Prose is free to differ (FR-14, contracts ``answer_query`` L3) and is never compared.

Cases were taken from the stub suite ``test/atdd/module12_contracts.test.py``
(``test_get_answer_evidence_*`` / ``test_get_citation_*``), which is never imported.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings

pytestmark = pytest.mark.api

FROZEN_START = "2026-10-16T15:00:00.000Z"
SESSIONS = "/api/v1/sessions"
SCENARIOS = {
    "S1": ("why was alex denied deepseek-coder", "access_denial_not_in_allowlist"),
    "S2": ("why can't group 4 run their fine-tuning job", "schedule_window_restricted"),
}
RUNS = 3
# the field that holds a record's own id, where it is not ``id``
IDENTITY_FIELD = {"policy": "clause_id", "window": "window_id", "event": "event_id"}


def fresh_client() -> TestClient:
    settings = Settings.from_env({"M12_CLOCK_START": FROZEN_START})
    return TestClient(create_app(settings), raise_server_exceptions=False)


def ask(client: TestClient, query: str) -> dict:
    created = client.post(SESSIONS, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    sid = created.json()["session_id"]
    response = client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": query})
    assert response.status_code == 200, response.json()
    return response.json()["answers"][0]


def citation(client: TestClient, cid: str):
    return client.get(f"/api/v1/citations/{quote(cid, safe='')}")


# -- AC 1 + AC 4: every claim is bound, every citation resolves (NFR-3: 100%) -----------------
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_claim_cites_only_its_own_evidence_set(scenario: str) -> None:
    query, diagnosis_class = SCENARIOS[scenario]
    with fresh_client() as client:
        answer = ask(client, query)
    assert answer["diagnosis_class"] == diagnosis_class and answer["canonical"] is None
    evidence_ids = [e["citation_id"] for e in answer["evidence"]]
    assert len(evidence_ids) == len(set(evidence_ids))  # unique by citation_id
    assert [e["position"] for e in answer["evidence"]] == list(range(len(evidence_ids)))
    assert answer["claims"], "a diagnosis without claims is no diagnosis"
    for claim in answer["claims"]:
        assert claim["claim_citations"], f"uncited claim: {claim['text']}"
        assert set(claim["claim_citations"]) <= set(evidence_ids)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_evidence_citation_resolves_through_the_citation_route(scenario: str) -> None:
    query, _ = SCENARIOS[scenario]
    with fresh_client() as client:
        answer = ask(client, query)
        stored = client.get(f"/api/v1/answers/{answer['answer_id']}/evidence")
        assert stored.status_code == 200 and stored.json() == {"evidence": answer["evidence"]}
        resolved = {
            e["citation_id"]: citation(client, e["citation_id"]) for e in answer["evidence"]
        }

    assert any(cid.startswith("clock#") for cid in resolved)  # the clock read is cited too
    for entry in answer["evidence"]:
        response = resolved[entry["citation_id"]]
        assert response.status_code == 200, (entry["citation_id"], response.json())
        assert response.json()["snippet"] == entry["snippet"]
        record = response.json()["source_record"]
        bare = entry["citation_id"].partition("#")[2]
        if entry["source_type"] == "clock":
            assert record == {"read_id": bare, "instant": FROZEN_START, "source": "clock"}
        else:  # the record the citation names: its own identity field, not any field
            assert record[IDENTITY_FIELD.get(entry["source_type"], "id")] == entry["citation_id"]


# -- AC 5: three fresh runs give identical evidence, citations, claims and class --------------
def evidence_fingerprint(answer: dict) -> dict:
    return {
        "evidence": [
            (e["citation_id"], e["source_type"], e["snippet"], e["position"])
            for e in answer["evidence"]
        ],
        "citations": sorted(
            {e["citation_id"] for e in answer["evidence"]}
            | {cid for claim in answer["claims"] for cid in claim["claim_citations"]}
        ),
        "claim_citations": [claim["claim_citations"] for claim in answer["claims"]],
        "diagnosis_class": answer["diagnosis_class"],
    }


@pytest.mark.determinism
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_three_runs_on_fresh_apps_with_a_frozen_clock_are_identical(scenario: str) -> None:
    query, diagnosis_class = SCENARIOS[scenario]
    runs = []
    for _ in range(RUNS):
        with fresh_client() as client:
            runs.append(evidence_fingerprint(ask(client, query)))

    assert len(runs) == RUNS
    assert runs[0] == runs[1] == runs[2]
    assert runs[0]["diagnosis_class"] == diagnosis_class
    # the clock citation is part of what must repeat, not something excluded from it
    assert [c for c in runs[0]["citations"] if c.startswith("clock#")] == [
        "clock#clk-0000000000000002"  # read 1 is taken by the session's created_at
    ]
    # the runs share one process and so one hash seed: order that leans on set or hash
    # iteration would repeat in all three, so the order is also pinned to the expected value
    expected_ids, expected_claims = PINNED[scenario]
    assert [e[0] for e in runs[0]["evidence"]] == expected_ids
    assert runs[0]["claim_citations"] == expected_claims


S1_CITED = ["user#alex", "model#deepseek-coder", "policy#catalog.4.2", "event#evt-4711"]
S2_CITED = ["group#group-4", "job#job-8823", "window#night", "clock#clk-0000000000000002"]
PINNED = {
    # user, model, policy clause, denial event, then the clock read (story 1.3 order)
    "S1": ([*S1_CITED, "clock#clk-0000000000000002"], [S1_CITED] * 3),
    # group, the blocked job, the window, then the clock read (story 3.1 order)
    "S2": (S2_CITED, [S2_CITED] * 3),
}
