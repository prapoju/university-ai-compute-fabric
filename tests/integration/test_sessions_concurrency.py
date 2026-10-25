"""NFR-6: >= 5 concurrent operator sessions, >= 50 queries/hour, no cross-session leakage.

Runs the real composition root (store, id generator, pipeline, service) with one OS thread per
operator session, on :memory: and on a file database.
"""

from __future__ import annotations

import statistics
import threading
import time
from pathlib import Path

import pytest

from src.bootstrap import Container, build_container
from src.config import Settings
from src.domain.result import is_ok
from src.dto import AnswerEnvelopeDTO
from src.ports.inbound import CanonicalOutcome, SessionUseCases
from src.ports.outbound import SessionStorePort

pytestmark = pytest.mark.integration

SESSIONS = 6  # NFR-6 asks for >= 5
QUERIES_EACH = 20


@pytest.fixture(params=["memory", "file"])
def container(request, tmp_path: Path):
    database = ":memory:" if request.param == "memory" else str(tmp_path / "m12.db")
    box = build_container(Settings.from_env({"M12_DB_PATH": database}))
    yield box
    box.close()


def _ok(result):
    assert is_ok(result), result
    return result.value


def _operator(use_cases: SessionUseCases, n: int, out: dict, timings: list[float]) -> None:
    """One operator: create a session, then alternate diagnoses, chit-chat and follow-ups."""
    started = time.perf_counter()
    session = _ok(use_cases.create_session("role-operations"))
    timings.append(time.perf_counter() - started)
    sent: list[str] = []
    for k in range(QUERIES_EACH):
        text = (
            f"why was user{n}x denied deepseek-coder attempt {k}"
            if k % 3 == 0
            else f"what is the weather for operator {n} turn {k}"
            if k % 3 == 1
            else f"and what about user{n}y turn {k}?"
        )
        sent.append(text)
        started = time.perf_counter()
        _ok(use_cases.submit_query(session.session_id, text))
        timings.append(time.perf_counter() - started)
    out[n] = (session.session_id, sent)


def _run_operators(container: Container) -> tuple[dict, list[float]]:
    use_cases = container.port(SessionUseCases)
    out: dict = {}
    timings: list[float] = []
    threads = [
        threading.Thread(target=_operator, args=(use_cases, n, out, timings))
        for n in range(SESSIONS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return out, timings


def test_parallel_operators_keep_their_sessions_apart(container: Container) -> None:
    out, _ = _run_operators(container)
    store = container.port(SessionStorePort)
    assert len(out) == SESSIONS

    all_answer_ids: list[str] = []
    for n, (sid, sent) in out.items():
        stored = _ok(store.get(sid)).session
        turns = _ok(store.list_turns(sid))
        # exactly this operator's turns, in the order they were sent
        assert [t.query for t in turns] == sent
        assert all(f"{n}" in t.query for t in turns)
        assert len(stored.context.prior_intents) == QUERIES_EACH
        assert stored.context.active_answer_ids == [t.answer_id for t in turns]
        all_answer_ids += stored.context.active_answer_ids
        # no other operator's text ever appears in this session
        others = [m for m in out if m != n]
        assert not any(
            f"user{m}x" in t.query or f"operator {m} " in t.query for t in turns for m in others
        )

    assert len(all_answer_ids) == SESSIONS * QUERIES_EACH == len(set(all_answer_ids))
    assert len({sid for sid, _ in out.values()}) == SESSIONS


def test_follow_up_context_never_crosses_between_concurrent_sessions(container: Container) -> None:
    use_cases = container.port(SessionUseCases)
    has_topic = _ok(use_cases.create_session("role-operations")).session_id
    fresh = _ok(use_cases.create_session("role-operations")).session_id
    _ok(use_cases.submit_query(has_topic, "why was alex denied deepseek-coder"))

    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def follow_up(label: str, sid: str) -> None:
        barrier.wait()
        results[label] = _ok(use_cases.submit_query(sid, "and what about mateo?"))

    threads = [
        threading.Thread(target=follow_up, args=("topic", has_topic)),
        threading.Thread(target=follow_up, args=("fresh", fresh)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert isinstance(results["topic"], AnswerEnvelopeDTO)  # inherited its own session topic
    assert isinstance(results["fresh"], CanonicalOutcome)  # the other session has none


def test_latency_stays_far_inside_the_contract_budgets(container: Container) -> None:
    _, timings = _run_operators(container)
    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1]
    # contracts.md: create/get p95 < 50 ms, submit p95 <= 3000 ms; generous margins, no sleeps
    assert p95 < 0.5, f"p95 {p95 * 1000:.1f} ms"
    assert statistics.mean(timings) < 0.1


def test_the_sustained_rate_requirement_is_met_by_orders_of_magnitude(container: Container) -> None:
    started = time.perf_counter()
    _run_operators(container)
    elapsed = time.perf_counter() - started
    queries = SESSIONS * QUERIES_EACH
    per_hour = queries / elapsed * 3600
    assert per_hour >= 50  # NFR-6: >= 50 queries/hour, sustained
    assert elapsed < 10.0
