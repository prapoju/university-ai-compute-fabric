"""`sim_telemetry` — scripted telemetry + fault generation driving the seeded fleet."""

from __future__ import annotations

import pytest

from support.fleet import TRIAGE_ERROR_CODE, TRIAGE_NODE_REF
from support.telemetry import FAULT, GPU_TEMP_C, HEARTBEAT

pytestmark = pytest.mark.unit


def test_script_thermal_fault_reproduces_s3(sim_telemetry, seed_fleet) -> None:
    emitted = sim_telemetry.script_thermal_fault(TRIAGE_NODE_REF)

    record = seed_fleet.get(TRIAGE_NODE_REF)
    assert record.status == "fault"
    assert record.cordoned is True
    assert record.error_code == TRIAGE_ERROR_CODE
    assert record.health == "fault"

    temps = [s.value for s in emitted if s.kind == GPU_TEMP_C]
    assert max(temps) >= 85
    fault_samples = [s for s in emitted if s.kind == FAULT]
    assert fault_samples and fault_samples[-1].value == TRIAGE_ERROR_CODE
    assert (seed_fleet.spec(TRIAGE_NODE_REF).node_id, TRIAGE_ERROR_CODE) in sim_telemetry.faults


def test_tick_heartbeats_every_healthy_node(sim_telemetry, seed_fleet) -> None:
    sim_telemetry.tick()
    beats = sim_telemetry.by_kind(HEARTBEAT)
    assert len(beats) == len(seed_fleet)
    assert {b.node_id for b in beats} == {s.node_id for s in seed_fleet}


def test_clock_advances_with_telemetry(sim_telemetry, fake_clock) -> None:
    before = fake_clock.current
    sim_telemetry.script_thermal_fault(TRIAGE_NODE_REF)
    assert fake_clock.current > before
    assert sim_telemetry.last().at == fake_clock.current


def test_unknown_node_is_rejected(sim_telemetry) -> None:
    with pytest.raises(KeyError):
        sim_telemetry.heartbeat("node#ws-gpu-99")


def test_restart_recovers_node(sim_telemetry, seed_fleet) -> None:
    sim_telemetry.script_thermal_fault(TRIAGE_NODE_REF)
    sim_telemetry.script_restart(TRIAGE_NODE_REF, error_code=TRIAGE_ERROR_CODE)
    record = seed_fleet.get(TRIAGE_NODE_REF)
    assert record.status == "available"
    assert record.cordoned is False
    assert record.error_code is None
