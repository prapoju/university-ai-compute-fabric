"""`seed_fleet` — heterogeneous estate per the hardware brief; OP-6 record shape."""

from __future__ import annotations

import pytest

from support.fleet import (
    BIG_GPU_COUNT,
    BIG_PER_GPU_VRAM_GB,
    DEFAULT_STANDARD_NODE_COUNT,
    NodeRecord,
    STANDARD_PER_GPU_VRAM_GB,
    TRIAGE_NODE_REF,
    build_fleet,
)

pytestmark = pytest.mark.unit


def test_fleet_is_many_24gb_plus_one_2x48gb(seed_fleet) -> None:
    assert len(seed_fleet) == DEFAULT_STANDARD_NODE_COUNT + 1
    standards = seed_fleet.standard_nodes
    assert len(standards) == DEFAULT_STANDARD_NODE_COUNT
    assert {s.total_vram_gb for s in standards} == {STANDARD_PER_GPU_VRAM_GB}
    assert seed_fleet.big_node.gpu_count == BIG_GPU_COUNT
    assert seed_fleet.big_node.per_gpu_vram_gb == BIG_PER_GPU_VRAM_GB
    assert seed_fleet.big_node.total_vram_gb == BIG_GPU_COUNT * BIG_PER_GPU_VRAM_GB


def test_fleet_starts_all_healthy(seed_fleet) -> None:
    seed_fleet.assert_all_healthy()
    assert seed_fleet.faulted() == []
    assert seed_fleet.cordoned() == []


def test_node_record_is_contract_exact(seed_fleet) -> None:
    record = seed_fleet.get(TRIAGE_NODE_REF)
    assert isinstance(record, NodeRecord)
    assert tuple(record.as_dict()) == NodeRecord.FIELDS           # §0.3: no extra fields
    assert record.id == "node#ws-gpu-11"
    assert record.hostname == "ws-gpu-11"
    assert record.gpu_memory_gb == STANDARD_PER_GPU_VRAM_GB


def test_big_node_record_reports_aggregate_vram(seed_fleet) -> None:
    big = seed_fleet.get(seed_fleet.big_node.node_id)
    assert big.gpu_memory_gb == 96


def test_get_unknown_node_returns_none(seed_fleet) -> None:
    assert seed_fleet.get("node#ws-gpu-99") is None          # OP-6 get -> NodeRecord|null


def test_scenario_s3_precondition_can_be_seeded(seed_fleet) -> None:
    seeded = seed_fleet.fault(TRIAGE_NODE_REF, "ERR_THERMAL_88")
    assert (seeded.status, seeded.cordoned, seeded.error_code, seeded.health) == (
        "fault", True, "ERR_THERMAL_88", "fault",
    )
    assert seed_fleet.select(status="fault") == [seeded]


def test_custom_size_is_tunable() -> None:
    small = build_fleet(standard_nodes=11)
    assert len(small) == 12
    assert small.get("node#ws-gpu-11") is not None            # S3 node still present
