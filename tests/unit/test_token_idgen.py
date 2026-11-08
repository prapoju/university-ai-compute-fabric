"""Gate tokens are unguessable; every other id stays deterministic (story 2.2, IR-06, FR-14)."""

from __future__ import annotations

import re

import pytest

from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.token_idgen import SecureTokenIdGen
from src.domain.result import Failure

pytestmark = pytest.mark.unit

TOKEN = re.compile(r"^gt-[0-9a-f]{32}$")


def test_every_token_has_the_contract_shape_and_is_unique() -> None:
    ids = SecureTokenIdGen(SimIdGen())
    tokens = [ids.new_id("gate_token").value for _ in range(500)]
    assert all(TOKEN.fullmatch(t) for t in tokens)
    assert len(set(tokens)) == 500


def test_two_generators_never_issue_the_same_first_token() -> None:
    first = SecureTokenIdGen(SimIdGen()).new_id("gate_token").value
    second = SecureTokenIdGen(SimIdGen()).new_id("gate_token").value
    assert first != second  # the deterministic generator would repeat gt-000...001


def test_the_deterministic_generator_alone_would_repeat_itself() -> None:
    assert SimIdGen().new_id("gate_token").value == SimIdGen().new_id("gate_token").value


def test_every_other_kind_is_delegated_and_stays_reproducible() -> None:
    ids = SecureTokenIdGen(SimIdGen())
    assert ids.new_id("answer").value == "ans-0000000000000001"
    assert ids.new_id("answer").value == "ans-0000000000000002"
    ids.new_id("gate_token")  # drawing a token does not move any other counter
    assert ids.new_id("answer").value == "ans-0000000000000003"


def test_a_counter_seeded_from_storage_is_honoured_for_the_other_kinds() -> None:
    ids = SecureTokenIdGen(SimIdGen.from_counters({"answer": 41}))
    assert ids.new_id("answer").value == "ans-000000000000002a"


PROPOSAL = re.compile(r"^prop-[0-9a-f]{16}$")


def test_a_proposal_id_has_the_contract_shape_and_cannot_be_predicted() -> None:
    """Review P-1: a guessable id plus the readable token lets anyone confirm (story 2.4)."""
    ids = SecureTokenIdGen(SimIdGen())
    found = [ids.new_id("proposal").value for _ in range(500)]
    assert all(PROPOSAL.fullmatch(p) for p in found) and len(set(found)) == 500
    assert found != [f"prop-{n:016x}" for n in range(1, 501)]  # not the counter's sequence
    other = SecureTokenIdGen(SimIdGen()).new_id("proposal").value
    assert other not in found  # two generators never start on the same id


def test_an_unknown_kind_is_the_typed_failure_of_the_inner_generator() -> None:
    result = SecureTokenIdGen(SimIdGen()).new_id("nope")
    assert isinstance(result, Failure) and result.code == "VALIDATION_BAD_ID_KIND"
