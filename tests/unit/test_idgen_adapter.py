"""The seeded id generator (OP-13): well-formed, unique, thread-safe, restart-safe (R2, E43)."""

from __future__ import annotations

import re
import threading
from pathlib import Path

import pytest

from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.config import PROJECT_ROOT
from src.domain.result import Failure, is_ok

pytestmark = pytest.mark.unit

# contracts.md section 0.1 IdString formats
FORMATS = {
    "session": r"sess-[0-9a-f]{16}",
    "answer": r"ans-[0-9a-f]{16}",
    "claim": r"clm-[0-9a-f]{16}",
    "tool_call": r"tc-[0-9a-f]{16}",
    "audit": r"aud-[0-9a-f]{16}",
    "proposal": r"prop-[0-9a-f]{16}",
    "gate_token": r"gt-[0-9a-f]{32}",
    "event": r"evt-[0-9a-f]{16}",
}


def _new(gen: SimIdGen, kind: str) -> str:
    result = gen.new_id(kind)
    assert is_ok(result), result
    return result.value


@pytest.mark.parametrize(("kind", "pattern"), sorted(FORMATS.items()))
def test_every_kind_matches_its_idstring_format(kind: str, pattern: str) -> None:
    assert re.fullmatch(pattern, _new(SimIdGen(), kind))


def test_the_first_ids_are_predictable_so_runs_are_reproducible() -> None:
    gen = SimIdGen()
    assert _new(gen, "session") == "sess-0000000000000001"
    assert _new(gen, "session") == "sess-0000000000000002"
    assert _new(gen, "answer") == "ans-0000000000000001"  # counters are per kind


def test_two_generators_issue_the_same_sequence() -> None:
    a, b = SimIdGen(), SimIdGen()
    assert [_new(a, "answer") for _ in range(5)] == [_new(b, "answer") for _ in range(5)]


def test_seeding_from_stored_counters_never_reissues_a_persisted_id() -> None:
    gen = SimIdGen.from_counters({"session": 5, "answer": 255})
    assert _new(gen, "session") == "sess-0000000000000006"
    assert _new(gen, "answer") == "ans-0000000000000100"  # 256 -> hex 100
    assert _new(gen, "event") == "evt-0000000000000001"  # kinds not stored start at 1


def test_an_unknown_kind_is_validation_bad_id_kind() -> None:
    result = SimIdGen().new_id("uuid")
    assert isinstance(result, Failure) and result.code == "VALIDATION_BAD_ID_KIND"


def test_ids_are_unique_across_threads() -> None:
    gen = SimIdGen()
    seen: list[str] = []

    def worker() -> None:
        seen.extend(_new(gen, "session") for _ in range(250))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(seen) == 2000 and len(set(seen)) == 2000


def test_the_adapter_draws_no_randomness_and_no_wall_clock() -> None:
    source = Path(PROJECT_ROOT / "src/adapters/outbound/sim/idgen_adapter.py").read_text("utf-8")
    for forbidden in ("import uuid", "import random", "import secrets", "import time", "datetime"):
        assert forbidden not in source
