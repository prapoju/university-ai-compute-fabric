"""The simulated prose writer (OP-14): deterministic, offline, and never a source of facts."""

from __future__ import annotations

import threading

import pytest

from src.adapters.outbound.sim.prose_adapter import SimProse
from src.domain.prose_guard import scan_prose
from src.domain.result import Failure, is_ok
from src.dto import ProsePromptDTO

pytestmark = pytest.mark.unit

SECTIONS = [
    "user#alex: Alex Rivera, role student",
    "policy#catalog.4.2 (RULE-CAT-04) [not-in-allowlist]: deepseek-coder requires CS-480",
]


def prompt(*sections: str) -> ProsePromptDTO:
    return ProsePromptDTO(
        evidence_sections=list(sections or SECTIONS), instruction="connect the findings"
    )


def test_the_default_prose_is_deterministic_non_empty_connective_text() -> None:
    writer = SimProse()
    first, second = writer.compose(prompt()), writer.compose(prompt("something else"))
    assert is_ok(first) and first == second and len(first.value.split()) >= 10


def test_the_default_prose_never_repeats_anything_from_the_evidence_sections() -> None:
    words = {w.strip(".,:;()[]#").casefold() for s in SECTIONS for w in s.split() if len(w) >= 3}
    assert scan_prose(SimProse().compose(prompt()).value, words) == []


def test_the_writer_records_what_it_was_asked_for_exactly_once_per_call() -> None:
    writer = SimProse()
    writer.compose(prompt())
    assert writer.call_count == 1
    assert writer.last_prompt.evidence_sections == SECTIONS  # evidence is passed as data
    writer.compose(prompt("another"))
    assert writer.call_count == 2


def test_a_scripted_output_is_returned_once_then_the_default_resumes() -> None:
    writer = SimProse()
    writer.script("scripted one", "scripted two")
    assert [writer.compose(prompt()).value for _ in range(3)][:2] == [
        "scripted one",
        "scripted two",
    ]
    assert writer.compose(prompt()).value == SimProse.DEFAULT


def test_an_injected_failure_is_llm_unavailable_and_recovers() -> None:
    writer = SimProse()
    writer.fail()
    result = writer.compose(prompt())
    assert isinstance(result, Failure) and result.code == "LLM_UNAVAILABLE"
    assert writer.call_count == 1  # the attempt still counts as a call
    writer.recover()
    assert is_ok(writer.compose(prompt()))


def test_concurrent_calls_are_all_counted() -> None:
    writer = SimProse()
    threads = [
        threading.Thread(target=lambda: [writer.compose(prompt()) for _ in range(100)])
        for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert writer.call_count == 600
