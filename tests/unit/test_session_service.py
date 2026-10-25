"""Story 1.2 - session lifecycle and conversational intake, at use-case level.

Runs against the real SQLite store (memory and file), a frozen SimClock and the seeded id
generator, so every assertion is about persisted, observable behaviour.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.sim.clock_adapter import SimClock
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.application.pipeline import AnswerPipeline, TurnOutput
from src.application.session_service import SessionService
from src.config import PROJECT_ROOT
from src.domain import canonical_strings as cs
from src.domain.result import Failure, Ok, is_ok
from src.dto import AnswerDTO, AnswerEnvelopeDTO, GetSessionResponse, SessionDTO
from src.ports.inbound import CanonicalOutcome

pytestmark = pytest.mark.unit

START = "2026-10-16T15:00:00.000Z"
S1 = "why was alex denied deepseek-coder"


@dataclass
class Rig:
    service: SessionService
    clock: SimClock
    store: SqliteSessionStore
    pipeline: AnswerPipeline


def build(database: str = ":memory:") -> Rig:
    connection = sqlite3.connect(database, check_same_thread=False)
    apply_migrations(connection, PROJECT_ROOT / "migrations")
    store = SqliteSessionStore(connection)
    clock = SimClock(START)
    pipeline = AnswerPipeline()
    service = SessionService(store=store, clock=clock, idgen=SimIdGen(), pipeline=pipeline)
    return Rig(service, clock, store, pipeline)


@pytest.fixture(params=["memory", "file"])
def rig(request, tmp_path: Path) -> Rig:
    return build(":memory:" if request.param == "memory" else str(tmp_path / "m12.db"))


def ok(result):
    assert is_ok(result), result
    return result.value


def new_session(rig: Rig) -> str:
    return ok(rig.service.create_session("role-operations")).session_id


def ask(rig: Rig, sid: str, text: str = S1):
    return rig.service.submit_query(sid, text)


# -- Scenario: Create a session ----------------------------------------------------------------
def test_create_session_returns_an_active_session_with_an_empty_context(rig: Rig) -> None:
    created = ok(rig.service.create_session("role-operations"))
    assert isinstance(created, SessionDTO)
    assert created.session_id == "sess-0000000000000001"
    assert created.created_at == START
    assert created.status == "active" and created.operator_role == "role-operations"
    assert created.context.model_dump() == {
        "resolved_entities": [], "prior_intents": [], "active_answer_ids": [],
    }  # fmt: skip
    assert ok(rig.store.get(created.session_id)).session == created


def test_session_ids_are_unique_and_sequential(rig: Rig) -> None:
    assert [new_session(rig) for _ in range(3)] == [f"sess-{n:016x}" for n in (1, 2, 3)]


@pytest.mark.parametrize(
    "role", ["admin", "role-", "role-UPPER", "role-" + "x" * 33, "", "role-a b"]
)
def test_a_malformed_operator_role_is_a_400_and_stores_nothing(rig: Rig, role: str) -> None:
    result = rig.service.create_session(role)
    assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"
    assert ok(rig.store.get("sess-0000000000000001")) is None
    assert new_session(rig) == "sess-0000000000000001"  # no id was consumed by the rejected call


# -- Scenario: Route the S1 query --------------------------------------------------------------
def test_the_s1_query_is_routed_to_access_denial_with_an_observation_only_answer(rig: Rig) -> None:
    sid = new_session(rig)
    envelope = ok(ask(rig, sid))
    assert isinstance(envelope, AnswerEnvelopeDTO) and len(envelope.answers) == 1
    answer = envelope.answers[0]
    assert answer.intent == "diagnose_access_denial"
    assert answer.answer_chain == ["observation"]
    assert answer.answer_id == "ans-0000000000000001" and answer.session_id == sid
    assert answer.query == S1 and answer.canonical is None and answer.diagnosis_class is None
    assert answer.claims == [] and answer.evidence == []
    assert "diagnose_access_denial" in answer.prose
    context = ok(rig.store.get(sid)).session.context
    assert context.prior_intents == ["diagnose_access_denial"]
    assert context.active_answer_ids == [answer.answer_id]


def test_the_same_query_again_is_a_new_turn_not_idempotent(rig: Rig) -> None:
    sid = new_session(rig)
    first = ok(ask(rig, sid)).answers[0]
    second = ok(ask(rig, sid)).answers[0]
    assert first.answer_id != second.answer_id
    context = ok(rig.store.get(sid)).session.context
    assert context.prior_intents == ["diagnose_access_denial"] * 2
    assert context.active_answer_ids == [first.answer_id, second.answer_id]


def test_the_stored_query_is_the_trimmed_text(rig: Rig) -> None:
    sid = new_session(rig)
    assert ok(ask(rig, sid, f"   {S1}  \n")).answers[0].query == S1


# -- Scenario: out-of-domain and compound-destructive are clarified ----------------------------
def test_an_out_of_domain_query_is_clarified_never_routed(rig: Rig) -> None:
    sid = new_session(rig)
    outcome = ok(ask(rig, sid, "what's the weather?"))
    assert outcome == CanonicalOutcome(
        code="CLARIFICATION_REQUIRED",
        message="Clarification required: no registered intent matches this query.",
    )
    turn = ok(rig.store.list_turns(sid))[0]
    assert (turn.intent, turn.canonical, turn.answer_chain) == (
        "clarification",
        "CLARIFICATION",
        ["observation"],
    )
    assert turn.prose == outcome.message
    assert ok(rig.store.get(sid)).session.context.prior_intents == ["clarification"]


def test_a_compound_query_with_a_destructive_verb_is_clarified(rig: Rig) -> None:
    sid = new_session(rig)
    outcome = ok(ask(rig, sid, "why was alex denied deepseek-coder and delete all his jobs"))
    assert outcome == CanonicalOutcome(
        "CLARIFICATION_REQUIRED", cs.clarification(cs.R_COMPOUND_DESTRUCTIVE)
    )
    assert ok(rig.store.list_turns(sid))[0].intent == "clarification"


# -- Scenario: Query validation ----------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "code", "message"),
    [
        (
            "",
            "VALIDATION_EMPTY_QUERY",
            "Query must contain between 1 and 1000 characters; received 0.",
        ),
        (
            "   \n ",
            "VALIDATION_EMPTY_QUERY",
            "Query must contain between 1 and 1000 characters; received 0.",
        ),
        ("a" * 1001, "VALIDATION_QUERY_TOO_LONG", "Query exceeds 1000 characters; received 1001."),
    ],
)
def test_invalid_queries_are_400_and_leave_no_trace(
    rig: Rig, text: str, code: str, message: str
) -> None:
    sid = new_session(rig)
    result = ask(rig, sid, text)
    assert isinstance(result, Failure) and (result.code, result.message) == (code, message)
    assert ok(rig.store.list_turns(sid)) == []
    assert ok(rig.store.get(sid)).session.context.prior_intents == []
    # neither an answer id nor a clock read was consumed by the rejected call
    assert ok(ask(rig, sid)).answers[0].answer_id == "ans-0000000000000001"
    assert ok(rig.clock.now()).read_id == "clk-0000000000000003"  # create + one real submit


def test_exactly_1000_characters_is_accepted(rig: Rig) -> None:
    sid = new_session(rig)
    result = ask(rig, sid, "a" * 1000)
    assert isinstance(ok(result), CanonicalOutcome)  # accepted, then clarified (no intent)


def test_validation_is_checked_before_the_session_lookup(rig: Rig) -> None:
    result = ask(rig, "sess-00000000000000ff", "")
    assert isinstance(result, Failure) and result.code == "VALIDATION_EMPTY_QUERY"


# -- Scenario: session states and idle expiry --------------------------------------------------
def test_an_absent_session_is_404_with_the_contract_message(rig: Rig) -> None:
    result = ask(rig, "sess-00000000000000ff")
    assert isinstance(result, Failure) and result.code == "SESSION_NOT_FOUND"
    assert result.message == "Session sess-00000000000000ff not found."


def test_a_session_idle_for_31_minutes_is_410_and_the_expiry_is_persisted(rig: Rig) -> None:
    sid = new_session(rig)
    rig.clock.advance(minutes=31)
    result = ask(rig, sid)
    assert isinstance(result, Failure) and result.code == "SESSION_EXPIRED"
    assert result.message == f"Session {sid} expired after 30 minutes idle."
    assert ok(rig.store.get(sid)).session.status == "expired"
    again = ask(rig, sid)  # the write-back is idempotent
    assert isinstance(again, Failure) and again.code == "SESSION_EXPIRED"


def test_exactly_30_minutes_idle_still_works_and_activity_resets_the_idle_timer(rig: Rig) -> None:
    sid = new_session(rig)
    rig.clock.advance(minutes=30)
    assert is_ok(ask(rig, sid))
    rig.clock.advance(minutes=30)  # 30 minutes after the last turn, not after creation
    assert is_ok(ask(rig, sid))
    rig.clock.advance(minutes=31)
    assert isinstance(ask(rig, sid), Failure)


def test_idle_time_counts_from_the_last_turn_not_from_creation(rig: Rig) -> None:
    sid = new_session(rig)
    rig.clock.advance(minutes=20)
    ok(ask(rig, sid))
    rig.clock.advance(minutes=20)  # 40 minutes since creation, 20 since the last turn
    assert is_ok(ask(rig, sid))


# -- Scenario: Read and reset ------------------------------------------------------------------
def test_get_session_returns_context_and_turns_in_order_and_changes_nothing(rig: Rig) -> None:
    sid = new_session(rig)
    first, second = ok(ask(rig, sid)).answers[0], ok(ask(rig, sid, "hello")) and None
    before = ok(rig.store.get(sid))
    read = ok(rig.service.get_session(sid))
    assert isinstance(read, GetSessionResponse)
    assert (read.session_id, read.status, read.operator_role) == (sid, "active", "role-operations")
    assert [t.answer_id for t in read.turns] == ["ans-0000000000000001", "ans-0000000000000002"]
    assert read.turns[0] == first and read.context.prior_intents == [
        "diagnose_access_denial",
        "clarification",
    ]
    assert ok(rig.store.get(sid)) == before  # idempotent read, no write
    assert second is None


def test_get_session_of_an_unknown_id_is_404(rig: Rig) -> None:
    result = rig.service.get_session("sess-00000000000000ff")
    assert isinstance(result, Failure) and result.code == "SESSION_NOT_FOUND"


def test_reset_clears_the_context_keeps_the_turns_and_is_idempotent(rig: Rig) -> None:
    sid = new_session(rig)
    ok(ask(rig, sid))
    assert ok(rig.service.reset_session(sid)) is None
    assert ok(rig.service.reset_session(sid)) is None
    read = ok(rig.service.get_session(sid))
    assert read.status == "reset"
    assert read.context.model_dump() == {
        "resolved_entities": [], "prior_intents": [], "active_answer_ids": [],
    }  # fmt: skip
    assert len(read.turns) == 1


def test_reset_of_an_unknown_session_is_404(rig: Rig) -> None:
    result = rig.service.reset_session("sess-00000000000000ff")
    assert isinstance(result, Failure) and result.code == "SESSION_NOT_FOUND"


def test_a_query_to_a_reset_session_is_410_and_persists_the_expiry(rig: Rig) -> None:
    sid = new_session(rig)
    ok(rig.service.reset_session(sid))
    result = ask(rig, sid)
    assert isinstance(result, Failure) and result.code == "SESSION_EXPIRED"
    assert ok(rig.store.get(sid)).session.status == "expired"  # contract P2 write-back


# -- Scenario: follow-up resolves from session context -----------------------------------------
def test_a_follow_up_is_routed_from_the_session_context(rig: Rig) -> None:
    sid = new_session(rig)
    ok(ask(rig, sid))
    answer = ok(ask(rig, sid, "and what about mateo?")).answers[0]
    assert answer.intent == "diagnose_access_denial"
    assert ok(rig.store.get(sid)).session.context.prior_intents == ["diagnose_access_denial"] * 2


def test_the_same_follow_up_in_a_fresh_session_is_clarified(rig: Rig) -> None:
    sid = new_session(rig)
    outcome = ok(ask(rig, sid, "and what about mateo?"))
    assert outcome == CanonicalOutcome(
        "CLARIFICATION_REQUIRED", cs.clarification(cs.R_FOLLOWUP_NO_CONTEXT)
    )


def test_a_follow_up_never_reaches_into_another_session(rig: Rig) -> None:
    first, second = new_session(rig), new_session(rig)
    ok(ask(rig, first))
    outcome = ok(ask(rig, second, "and what about mateo?"))
    assert isinstance(outcome, CanonicalOutcome)  # session B has no earlier topic of its own


# -- time, determinism, failures ---------------------------------------------------------------
def test_exactly_one_clock_read_per_call(rig: Rig) -> None:
    sid = new_session(rig)  # read 1
    ok(ask(rig, sid))  # read 2
    ok(rig.service.reset_session(sid))  # read 3
    assert ok(rig.clock.now()).read_id == "clk-0000000000000004"


def test_a_clock_failure_is_503_and_changes_nothing(rig: Rig) -> None:
    sid = new_session(rig)
    rig.clock.fail()
    for result in (
        rig.service.create_session("role-operations"),
        ask(rig, sid),
        rig.service.reset_session(sid),
    ):
        assert isinstance(result, Failure) and result.code == "CLOCK_UNAVAILABLE"
    rig.clock.recover()
    assert ok(rig.store.list_turns(sid)) == []
    assert ok(rig.store.get(sid)).session.status == "active"


def test_a_store_failure_is_a_typed_503_not_an_exception(rig: Rig) -> None:
    sid = new_session(rig)
    rig.store._connection.close()  # noqa: SLF001
    for result in (rig.service.create_session("role-operations"), ask(rig, sid),
                   rig.service.get_session(sid), rig.service.reset_session(sid)):  # fmt: skip
        assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_two_fresh_services_given_the_same_script_produce_identical_results() -> None:
    def script() -> list[object]:
        rig = build()
        sid = new_session(rig)
        out = [ok(ask(rig, sid)), ok(ask(rig, sid, "what's the weather?")), ok(ask(rig, sid))]
        out.append(ok(rig.service.get_session(sid)))
        return out

    assert script() == script()


# -- the pipeline seam for stories 1.3 / 3.1 / 4.1 ---------------------------------------------
def test_a_registered_handler_replaces_the_observation_only_answer(rig: Rig) -> None:
    def handler(turn) -> Ok:
        answer = AnswerDTO(
            answer_id=turn.answer_id, session_id=turn.session_id, query=turn.query,
            intent="diagnose_access_denial", answer_chain=["observation", "evidence"],
            claims=[], evidence=[], prose="handled",
        )  # fmt: skip
        return Ok(
            TurnOutput(answer=answer, resolved_entities=("user#alex", "model#deepseek-coder"))
        )

    rig.pipeline.register("diagnose_access_denial", handler)
    sid = new_session(rig)
    answer = ok(ask(rig, sid)).answers[0]
    assert (answer.prose, answer.answer_chain) == ("handled", ["observation", "evidence"])
    context = ok(rig.store.get(sid)).session.context
    assert context.resolved_entities == ["user#alex", "model#deepseek-coder"]  # superset rule (Q2)


def test_a_handler_failure_aborts_the_turn_with_no_partial_state(rig: Rig) -> None:
    rig.pipeline.register(
        "diagnose_access_denial", lambda turn: Failure("PROVIDER_UNAVAILABLE", observed=("boom",))
    )
    sid = new_session(rig)
    result = ask(rig, sid)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert ok(rig.store.list_turns(sid)) == []
    assert ok(rig.store.get(sid)).session.context.prior_intents == []


# -- serialization within one session ----------------------------------------------------------
def test_parallel_queries_in_one_session_are_serialized_without_lost_updates(rig: Rig) -> None:
    sid = new_session(rig)
    results: list[object] = []

    def worker() -> None:
        results.extend(ask(rig, sid) for _ in range(10))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(is_ok(r) for r in results) and len(results) == 60
    context = ok(rig.store.get(sid)).session.context
    assert len(context.prior_intents) == 60
    assert len(set(context.active_answer_ids)) == 60
    assert len(ok(rig.store.list_turns(sid))) == 60


# -- review patches (story 1.2 code review) ----------------------------------------------------
class TickingClock(SimClock):
    """A simulated clock that moves one second forward on every read, like a real one."""

    def now(self):
        result = super().now()
        self.advance(seconds=1)
        return result


def build_ticking() -> Rig:
    rig = build()
    rig.service = SessionService(
        store=rig.store,
        clock=(ticking := TickingClock(START)),
        idgen=SimIdGen(),
        pipeline=rig.pipeline,
    )
    rig.clock = ticking
    return rig


def test_a_clock_failure_on_an_unknown_session_is_404_not_503(rig: Rig) -> None:
    rig.clock.fail()
    for result in (
        ask(rig, "sess-00000000000000ff"),
        rig.service.reset_session("sess-00000000000000ff"),
    ):
        assert isinstance(result, Failure) and result.code == "SESSION_NOT_FOUND"


def test_concurrent_turns_are_stored_in_clock_order(rig: Rig) -> None:
    ticking = build_ticking()
    sid = new_session(ticking)

    def worker() -> None:
        for _ in range(10):
            assert is_ok(ticking.service.submit_query(sid, S1))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    turns = ok(ticking.store.list_turns(sid))
    context = ok(ticking.store.get(sid)).session.context
    assert [t.answer_id for t in turns] == context.active_answer_ids  # same order everywhere
    stamps = [
        row[0]
        for row in ticking.store._connection.execute(  # noqa: SLF001
            "select created_at from answers where session_id = ? order by answer_id", (sid,)
        )
    ]
    assert stamps == sorted(stamps)  # a later answer never carries an earlier time


def test_a_corrupt_stored_instant_is_a_typed_failure_not_a_raw_exception(rig: Rig) -> None:
    sid = new_session(rig)
    # matches the table's GLOB check but is not a real date
    rig.store._connection.execute(  # noqa: SLF001
        "update sessions set created_at = '2026-13-45T00:00:00.000Z' where session_id = ?", (sid,)
    )
    rig.store._connection.commit()  # noqa: SLF001
    result = ask(rig, sid)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_a_failed_expiry_write_does_not_hide_the_410(rig: Rig) -> None:
    sid = new_session(rig)
    rig.clock.advance(minutes=31)
    rig.store.mark_expired = lambda *args: Failure("PROVIDER_UNAVAILABLE", observed=("disk full",))
    result = ask(rig, sid)
    assert isinstance(result, Failure) and result.code == "SESSION_EXPIRED"


def test_get_session_is_a_consistent_snapshot_while_turns_are_being_written(rig: Rig) -> None:
    sid = new_session(rig)
    stop = threading.Event()
    problems: list[str] = []

    def writer() -> None:
        while not stop.is_set():
            ask(rig, sid)

    def reader() -> None:
        for _ in range(150):
            read = ok(rig.service.get_session(sid))
            if [t.answer_id for t in read.turns] != read.context.active_answer_ids:
                problems.append("context and turns disagree")

    writers = [threading.Thread(target=writer) for _ in range(3)]
    for thread in writers:
        thread.start()
    reader()
    stop.set()
    for thread in writers:
        thread.join()
    assert problems == []


def test_duplicate_entities_from_one_handler_are_stored_once(rig: Rig) -> None:
    def handler(turn) -> Ok:
        answer = AnswerDTO(
            answer_id=turn.answer_id, session_id=turn.session_id, query=turn.query,
            intent="diagnose_access_denial", answer_chain=["observation"],
            claims=[], evidence=[], prose="handled",
        )  # fmt: skip
        entities = ("user#alex", "user#alex", "model#deepseek-coder", "user#alex")
        return Ok(TurnOutput(answer=answer, resolved_entities=entities))

    rig.pipeline.register("diagnose_access_denial", handler)
    sid = new_session(rig)
    ok(ask(rig, sid))
    ok(ask(rig, sid))
    context = ok(rig.store.get(sid)).session.context
    assert context.resolved_entities == ["user#alex", "model#deepseek-coder"]
