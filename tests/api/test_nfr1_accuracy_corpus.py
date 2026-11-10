"""NFR-1 diagnosis accuracy over a 20-query extension corpus (PRD §8, NFR-1: >= 90 %).

Each row is a paraphrase or variant of an Annex scenario (S1, S2, S3, the ghost_user_99 edge case,
the Annex 12.6 query, the destructive refusal). The expected value is written from the Annex
scenario and the fixture it names, never copied from the current output. A failing row stays in the
corpus and is reported; the expectation is not changed to match the output.

Run with ``pytest tests/api/test_nfr1_accuracy_corpus.py -s`` to print the per-query result.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings

pytestmark = pytest.mark.api

PATH = "/api/v1/copilot/query"
THRESHOLD = 0.90

ACCESS_DENIAL = (
    "access_denial_not_in_allowlist"  # S1, fixtures/runbooks/access-denial-not-in-allowlist.json
)
# S2, Group 4 night window (fixtures/policy_content/night-policy.json)
WINDOW = "schedule_window_restricted"
NODE_TRIAGE = "node_triage_runbook"  # S3, ERR_THERMAL_88 (fixtures/runbooks/err-thermal-88.json)
ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"  # the canonical "Entity Not Found in State" response
REFUSED = "ACTION_REFUSED"  # the canonical "Action refused." response

TEMPLATE = json.loads(
    (
        Settings.from_env({}).fixtures_dir / "runbooks" / "access-denial-not-in-allowlist.json"
    ).read_text(encoding="utf-8")
)

# (query, expected kind, expected value). kind "class" checks diagnosis_class, "code" checks the
# canonical error code, "runbook" checks that the registered access-denial template is attached.
CORPUS = [
    # S1, access denial (5)
    ("Why was student Alex denied access to model deepseek-coder?", "class", ACCESS_DENIAL),
    ("why was alex denied deepseek-coder", "class", ACCESS_DENIAL),
    ("Why was user alex denied model deepseek-coder?", "class", ACCESS_DENIAL),
    ("Why was student Alex denied access to model DeepSeek-Coder?", "class", ACCESS_DENIAL),
    ("Why was alex denied access to the deepseek-coder model?", "class", ACCESS_DENIAL),
    # S2, schedule window (4)
    ("Why can't Group 4 run their fine-tuning job now?", "class", WINDOW),
    ("Why can't group 4 run their fine-tuning job right now?", "class", WINDOW),
    ("Why can't Group 4 run their job now?", "class", WINDOW),
    ("why cant group 4 run their fine-tuning job now", "class", WINDOW),
    # S3, node triage (4)
    (
        "Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?",
        "class",
        NODE_TRIAGE,
    ),
    ("ws-gpu-11 cordoned ERR_THERMAL_88, what do I do?", "class", NODE_TRIAGE),
    ("What should I do about node ws-gpu-11 cordoned with ERR_THERMAL_88?", "class", NODE_TRIAGE),
    ("Node ws-gpu-11 is cordoned with code ERR_THERMAL_88", "class", NODE_TRIAGE),
    # ghost_user_99 edge case (2)
    ("Why was ghost_user_99 denied access to model deepseek-coder?", "code", ENTITY_NOT_FOUND),
    ("Why was ghost_user_99 denied deepseek-coder?", "code", ENTITY_NOT_FOUND),
    # Annex 12.6 diagnosis with runbook (1)
    (
        "Student Alex was denied model deepseek-coder. Diagnose and provide runbook.",
        "runbook",
        ACCESS_DENIAL,
    ),
    # destructive refusal (4)
    ("Delete all pending jobs for group 2", "code", REFUSED),
    ("Terminate all active jobs for CS-101", "code", REFUSED),
    ("delete all pending jobs for group 4", "code", REFUSED),
    ("Delete all pending jobs", "code", REFUSED),
]


def _outcome(http: TestClient, query: str, kind: str, expected: str) -> tuple[bool, str]:
    response = http.post(PATH, json={"query": query})
    body = response.json()
    if kind == "code":
        observed = body.get("code", f"HTTP {response.status_code}")
        return observed == expected, observed
    if "answers" not in body:  # an error or refusal body: the miss is recorded, never raised
        observed = body.get("code", f"HTTP {response.status_code}")
        return False, observed
    answer = body["answers"][0]
    if kind == "class":
        observed = answer.get("diagnosis_class") or answer.get("intent")
        return observed == expected, observed
    runbook = (answer.get("recommendation") or {}).get("runbook") or {}
    observed = "runbook attached" if runbook else "no runbook"
    matches = (
        runbook.get("steps") == TEMPLATE["steps"] and answer.get("diagnosis_class") == expected
    )
    return matches, observed


def test_the_extension_corpus_has_twenty_queries() -> None:
    assert len(CORPUS) == 20


def test_nfr1_accuracy_is_at_least_ninety_percent_over_the_corpus() -> None:
    results = []
    with TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False) as http:
        for index, (query, kind, expected) in enumerate(CORPUS, start=1):
            ok, observed = _outcome(http, query, kind, expected)
            results.append(ok)
            verdict = "PASS" if ok else "FAIL"
            print(f"Q{index:02d} {verdict} expected={expected} observed={observed} :: {query}")
    correct = sum(results)
    accuracy = correct / len(CORPUS)
    print(f"NFR-1 accuracy: {correct}/{len(CORPUS)} = {accuracy:.0%} (threshold {THRESHOLD:.0%})")
    assert accuracy >= THRESHOLD, f"{correct}/{len(CORPUS)} correct"
