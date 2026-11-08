"""Story 3.3 - annex 12.6 attaches the access-denial runbook; S1, S2, ghost_user_99 do not change.

The bodies of S1, S2 and ``ghost_user_99`` were captured at HEAD before this story changed any code
(``tests/api/golden/copilot_query_at_head.json``). They are compared byte for byte.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings

pytestmark = pytest.mark.api

GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "copilot_query_at_head.json").read_text(encoding="utf-8")
)
QUERIES = {
    "s1": "Why was student Alex denied access to model deepseek-coder?",
    "s2": "Why can't group 4 run their fine-tuning job right now?",
    "ghost": "Why was ghost_user_99 denied access to model deepseek-coder?",
}
ANNEX_12_6 = "Student Alex was denied model deepseek-coder. Diagnose and provide runbook."
TEMPLATE = json.loads(
    (
        Settings.from_env({}).fixtures_dir / "runbooks" / "access-denial-not-in-allowlist.json"
    ).read_text(encoding="utf-8")
)


def post(query: str) -> str:
    """The raw body, on a fresh application as the golden bodies were captured."""
    with TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False) as client:
        response = client.post("/api/v1/copilot/query", json={"query": query})
    assert response.status_code == 200
    return response.text


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_the_mandatory_query_body_is_byte_identical_to_head(name: str) -> None:
    assert post(QUERIES[name]) == GOLDEN[name]


def test_s1_carries_no_runbook() -> None:
    assert json.loads(GOLDEN["s1"])["answers"][0]["recommendation"] is None


def answer_of(query: str) -> dict:
    return json.loads(post(query))["answers"][0]


def test_the_annex_query_attaches_the_registered_runbook_verbatim() -> None:
    answer = answer_of(ANNEX_12_6)
    assert answer["intent"] == "diagnose_access_denial"
    assert answer["diagnosis_class"] == "access_denial_not_in_allowlist"
    assert answer["answer_chain"] == ["observation", "evidence", "diagnosis", "recommendation"]
    assert answer["recommendation"] == {
        "runbook": {
            "steps": TEMPLATE["steps"],
            "required_tools": TEMPLATE["required_tools"],
            "safety_warnings": TEMPLATE["safety_warnings"],
            "provenance": {
                "source": TEMPLATE["approved_source"],
                "version": TEMPLATE["version"],
            },
        }
    }


def test_the_annex_query_keeps_the_claims_and_evidence_of_s1() -> None:
    annex, s1 = answer_of(ANNEX_12_6), answer_of(QUERIES["s1"])
    assert annex["claims"] == s1["claims"]
    assert annex["evidence"] == s1["evidence"]
    assert annex["diagnosis_class"] == s1["diagnosis_class"]
