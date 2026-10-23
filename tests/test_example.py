"""Smoke test: proves every mandatory fixture is wired and usable together.

Copy these patterns when adding suites. Nothing here imports Module 12 source (none
exists yet) — the harness is independently runnable.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from support.clock import READ_ID_RE, FakeClock, parse_instant

pytestmark = pytest.mark.unit


def test_all_mandatory_fixtures_are_wired(
    fake_clock, seed_fleet, sim_telemetry, db, explain_assert, sample,
) -> None:
    # estate + telemetry reproduce S3
    sim_telemetry.script_thermal_fault("node#ws-gpu-11")
    node = seed_fleet.get("node#ws-gpu-11")
    assert (node.status, node.cordoned, node.error_code) == ("fault", True, "ERR_THERMAL_88")

    # a decision cites its rule, its observed values, and its citations
    explain_assert(
        {
            "intent": {"intent_code": "diagnose_node_triage", "matched_rule_id": "rule.node_triage"},
            "observed": {"error_code": node.error_code, "cordoned": node.cordoned},
            "claim_citations": ["node#ws-gpu-11", fake_clock.now().citation_id],
        },
        rule_id="rule.node_triage",
        values={"error_code": "ERR_THERMAL_88"},
    )

    # the migrated store accepts a schema-valid session
    db.insert("sessions", sample.session_row())
    assert db.count("sessions") == 1


async def test_harness_runs_under_asyncio(fake_clock, seed_fleet) -> None:
    assert fake_clock.now().source == "clock"
    assert len(seed_fleet) >= 2


@pytest.mark.determinism
@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=25)
def test_clock_reads_are_unique_formatted_and_monotonic(n: int) -> None:
    clock = FakeClock()
    reads = [clock.now() for _ in range(n)]
    ids = [r.read_id for r in reads]
    instants = [parse_instant(r.instant) for r in reads]
    assert len(set(ids)) == n
    assert all(READ_ID_RE.match(i) for i in ids)
    assert instants == sorted(instants)
