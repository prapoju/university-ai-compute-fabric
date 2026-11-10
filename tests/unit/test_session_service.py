"""Story 1.2 - session lifecycle and conversational intake, at use-case level.

Runs against the real SQLite store (memory and file), a frozen SimClock and the seeded id
generator, so every assertion is about persisted, observable behaviour.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.adapters.outbound.db.audit_store import SqliteAuditStore
from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.adapters.outbound.sim.clock_adapter import SimClock
from src.adapters.outbound.sim.fixtures_adapter import SimProviders, SimRunbookRegistry
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.sim.prose_adapter import SimProse
from src.application.access_denial_handler import AccessDenialHandler
from src.application.audit_writer import AuditWriter
from src.application.entity_resolver import EntityResolver
from src.application.evidence_assembler import EvidenceAssembler
from src.application.parallel_reads import ParallelReads
from src.application.pipeline import AnswerPipeline, TurnOutput
from src.application.session_service import SessionService
from src.application.tool_audit import TOOL_PORT_NAMES, ToolCallRecorder, audited
from src.config import PROJECT_ROOT
from src.domain import canonical_strings as cs
from src.domain.result import Failure, Ok, is_ok
from src.domain.session_rules import empty_context
from src.dto import AnswerDTO, AnswerEnvelopeDTO, GetSessionResponse, SessionDTO
from src.ports.inbound import CanonicalOutcome
from src.ports.outbound import CatalogPort, EventStorePort, PolicyPort, UsersPort

pytestmark = pytest.mark.unit

START = "2026-10-16T15:00:00.000Z"
S1 = "why was alex denied deepseek-coder"


@dataclass
class Rig:
    service: SessionService
    clock: SimClock
    store: SqliteSessionStore
    pipeline: AnswerPipeline
    writer: SqliteWriter
    audit: SqliteAuditStore
    recorder: ToolCallRecorder
    idgen: SimIdGen


def service_for(rig: Rig, clock: SimClock, idgen: SimIdGen) -> SessionService:
    return SessionService(
        store=rig.store, clock=clock, idgen=idgen, pipeline=rig.pipeline, uow=rig.writer,
        audit=AuditWriter(rig.audit, idgen), recorder=rig.recorder,
    )  # fmt: skip


def build(database: str = ":memory:", retention_cap: int = 10_000) -> Rig:
    writer = SqliteWriter.open(database)
    apply_migrations(writer, PROJECT_ROOT / "migrations")
    store = SqliteSessionStore(writer)
    clock = SimClock(START)
    pipeline = AnswerPipeline()
    idgen = SimIdGen()
    rig = Rig(
        None, clock, store, pipeline, writer, SqliteAuditStore(writer, retention_cap),
        ToolCallRecorder(), idgen,
    )  # fmt: skip
    rig.service = service_for(rig, clock, idgen)
    return rig


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
    rig.store._writer._connection.close()  # noqa: SLF001
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
    ticking = TickingClock(START)
    rig.idgen = SimIdGen()
    rig.service = service_for(rig, ticking, rig.idgen)
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
        for row in ticking.store._writer._connection.execute(  # noqa: SLF001
            "select created_at from answers where session_id = ? order by answer_id", (sid,)
        )
    ]
    assert stamps == sorted(stamps)  # a later answer never carries an earlier time


def test_a_corrupt_stored_instant_is_a_typed_failure_not_a_raw_exception(rig: Rig) -> None:
    sid = new_session(rig)
    # matches the table's GLOB check but is not a real date
    rig.store._writer._connection.execute(  # noqa: SLF001
        "update sessions set created_at = '2026-13-45T00:00:00.000Z' where session_id = ?", (sid,)
    )
    result = ask(rig, sid)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_a_failed_expiry_write_does_not_hide_the_410(rig: Rig) -> None:
    sid = new_session(rig)
    rig.clock.advance(minutes=31)
    rig.store.mark_expired = lambda *args: Failure("PROVIDER_UNAVAILABLE", observed=("disk full",))
    result = ask(rig, sid)
    assert isinstance(result, Failure) and result.code == "SESSION_EXPIRED"


def test_an_answer_that_could_not_be_saved_is_never_returned(rig: Rig) -> None:
    failing, healthy = new_session(rig), new_session(rig)
    # the context UPDATE is append_turn's last statement: the answer row is already inserted in
    # the open transaction when it aborts, so only the store's rollback can remove it
    connection = rig.store._writer._connection  # noqa: SLF001
    connection.execute(
        "CREATE TEMP TRIGGER disk_full BEFORE UPDATE ON sessions"
        f" WHEN NEW.session_id = '{failing}' AND NEW.last_turn_at IS NOT NULL"
        " BEGIN SELECT RAISE(ABORT, 'disk full'); END"
    )

    result = ask(rig, failing)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert ok(rig.store.list_turns(failing)) == []
    orphans = connection.execute("SELECT count(*) FROM answers WHERE session_id = ?", (failing,))
    assert orphans.fetchone() == (0,)
    assert ok(rig.store.get(failing)).session.context == empty_context()

    answer = ok(ask(rig, healthy)).answers[0]  # the failure is scoped to one session
    assert [turn.answer_id for turn in ok(rig.store.list_turns(healthy))] == [answer.answer_id]


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


def test_a_reused_entity_moves_to_the_end_so_follow_ups_use_the_latest(rig: Rig) -> None:
    """Review patch: the context is ordered by most recent use, not by first appearance."""
    turns = iter(
        [
            ("user#alex", "model#deepseek-coder"),
            ("user#sofia", "model#llama-3-8b-instruct"),
            ("user#sofia", "model#deepseek-coder"),  # deepseek-coder is used again
        ]
    )

    def handler(turn) -> Ok:
        answer = AnswerDTO(
            answer_id=turn.answer_id, session_id=turn.session_id, query=turn.query,
            intent="diagnose_access_denial", answer_chain=["observation"],
            claims=[], evidence=[], prose="p",
        )  # fmt: skip
        return Ok(TurnOutput(answer=answer, resolved_entities=next(turns)))

    rig.pipeline.register("diagnose_access_denial", handler)
    sid = new_session(rig)
    for _ in range(3):
        ok(ask(rig, sid))
    context = ok(rig.store.get(sid)).session.context
    assert context.resolved_entities == [
        "user#alex", "model#llama-3-8b-instruct", "user#sofia", "model#deepseek-coder",
    ]  # fmt: skip


# -- story 1.5: every stored turn is audited, atomically with its Answer (FR-11, AD-10, D1) -----
S1_TOOL_CALLS = [
    "toolcall.answer_query",
    "toolcall.users_port.get",
    "toolcall.catalog_port.get",
    "toolcall.policy_port.for_model",
    "toolcall.event_store_port.query",
]


class _DownUsers(UsersPort):
    def get(self, id):
        return Failure("PROVIDER_UNAVAILABLE", observed=("users down",))

    def browse(self, q, page, page_size):
        return Failure("PROVIDER_UNAVAILABLE", observed=("users down",))

    def by_ids(self, ids):
        return Failure("PROVIDER_UNAVAILABLE", observed=("users down",))


def audited_rig(database: str = ":memory:", *, users: UsersPort | None = None) -> Rig:
    """The rig with the real S1 diagnoser reading through audited fixture ports."""
    rig = build(database)
    providers = SimProviders.from_fixtures(PROJECT_ROOT / "fixtures", START)
    raw = {**providers.as_ports(), **({UsersPort: users} if users else {})}
    ports = {
        port: audited(port, raw[port], name=name, recorder=rig.recorder)
        for port, name in TOOL_PORT_NAMES.items()
    }
    rig.pipeline.register(
        "diagnose_access_denial",
        AccessDenialHandler(
            resolver=EntityResolver(users=ports[UsersPort], catalog=ports[CatalogPort]),
            assembler=EvidenceAssembler(
                policy=ports[PolicyPort],
                events=ports[EventStorePort],
                reads=ParallelReads(recorder=rig.recorder),
            ),
            prose=SimProse(),
            idgen=rig.idgen,
            runbooks=SimRunbookRegistry(()),
        ),
    )
    return rig


@pytest.fixture(params=["memory", "file"])
def arig(request, tmp_path: Path) -> Rig:
    return audited_rig(":memory:" if request.param == "memory" else str(tmp_path / "m12.db"))


def audit_rows(rig: Rig, sid: str) -> list:
    entries, total = ok(rig.audit.page(sid, 0, 100))
    assert total == len(entries)
    return entries


def count(rig: Rig, table: str) -> int:
    with rig.writer.read() as db:
        return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_an_s1_turn_writes_one_row_per_tool_call_in_call_order(arig: Rig) -> None:
    sid = new_session(arig)
    answer = ok(ask(arig, sid)).answers[0]
    rows = audit_rows(arig, sid)
    assert [r.result_summary["tool_name"] for r in rows] == S1_TOOL_CALLS
    assert [r.audit_id for r in rows] == [f"aud-{n:016x}" for n in range(1, 6)]
    assert [r.tool_call_id for r in rows] == [f"tc-{n:016x}" for n in range(1, 6)]
    assert {r.timestamp for r in rows} == {START}
    assert {(r.session_id, r.operator_role, r.actor) for r in rows} == {
        (sid, "role-operations", "copilot")
    }
    assert rows[0].result_summary["diagnosis_class"] == answer.diagnosis_class
    assert count(arig, "tool_calls") == count(arig, "audit_records") == 5
    with arig.writer.read() as db:
        params = db.execute(
            "SELECT params_summary FROM tool_calls WHERE tool_call_id = 'tc-0000000000000001'"
        ).fetchone()[0]
    assert S1 not in params and "answer_id" in params  # the query text is never stored


def test_a_canonical_entity_not_found_turn_is_audited(arig: Rig) -> None:
    sid = new_session(arig)
    outcome = ok(ask(arig, sid, "why was ghost denied deepseek-coder"))
    assert isinstance(outcome, CanonicalOutcome) and outcome.code == "ENTITY_NOT_FOUND"
    rows = audit_rows(arig, sid)
    assert rows[0].result_summary == {
        "tool_name": "toolcall.answer_query", "status": "ok", "canonical": "ENTITY_NOT_FOUND",
    }  # fmt: skip
    assert rows[1].result_summary == {
        "tool_name": "toolcall.users_port.get", "status": "ok", "result_count": 0,
    }  # fmt: skip


def test_a_503_turn_writes_no_audit_row_and_draws_no_audit_id() -> None:
    down = audited_rig(users=_DownUsers())
    sid = new_session(down)
    result = ask(down, sid)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert count(down, "tool_calls") == count(down, "audit_records") == 0
    assert ok(down.idgen.new_id("tool_call")) == "tc-0000000000000001"
    assert ok(down.idgen.new_id("audit")) == "aud-0000000000000001"


def test_404_410_and_400_turns_write_no_audit_row(arig: Rig) -> None:
    sid = new_session(arig)
    assert ask(arig, "sess-00000000000000ff").code == "SESSION_NOT_FOUND"
    assert ask(arig, sid, "   ").code == "VALIDATION_EMPTY_QUERY"
    arig.clock.advance(minutes=31)
    assert ask(arig, sid).code == "SESSION_EXPIRED"
    assert count(arig, "tool_calls") == count(arig, "audit_records") == 0
    fresh = new_session(arig)
    ok(ask(arig, fresh))
    assert audit_rows(arig, fresh)[0].tool_call_id == "tc-0000000000000001"  # nothing drawn


def test_an_audit_write_failure_rolls_back_the_answer_too(arig: Rig) -> None:
    sid = new_session(arig)
    with arig.writer.read() as db:
        db.execute(
            "CREATE TEMP TRIGGER audit_disk_full BEFORE INSERT ON audit_records"
            " BEGIN SELECT RAISE(ABORT, 'disk full'); END"
        )
    result = ask(arig, sid)
    assert isinstance(result, Failure) and result.code == "AUDIT_WRITE_FAILED"
    assert result.message == "Audit write failed for tool call tc-0000000000000001."
    assert ok(arig.store.list_turns(sid)) == []
    assert count(arig, "answers") == count(arig, "tool_calls") == 0
    stored = ok(arig.store.get(sid))
    assert stored.session.context == empty_context() and stored.last_turn_at is None


def test_an_answer_write_failure_writes_no_audit_row(arig: Rig) -> None:
    sid = new_session(arig)
    with arig.writer.read() as db:
        db.execute(
            "CREATE TEMP TRIGGER answers_disk_full BEFORE INSERT ON answers"
            " BEGIN SELECT RAISE(ABORT, 'disk full'); END"
        )
    result = ask(arig, sid)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert count(arig, "tool_calls") == count(arig, "audit_records") == 0


def test_a_commit_failure_is_a_typed_503(arig: Rig) -> None:
    sid = new_session(arig)
    arig.writer.close()
    result = arig.service.reset_session(sid)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_an_idgen_failure_while_minting_audit_ids_stores_nothing(arig: Rig) -> None:
    sid = new_session(arig)
    real = arig.idgen.new_id
    arig.idgen.new_id = lambda kind: (
        Failure("PROVIDER_UNAVAILABLE", observed=("idgen down",)) if kind == "audit" else real(kind)
    )
    assert ask(arig, sid).code == "PROVIDER_UNAVAILABLE"
    assert arig.service.reset_session(sid).code == "PROVIDER_UNAVAILABLE"
    assert ok(arig.store.list_turns(sid)) == []
    assert ok(arig.store.get(sid)).session.status == "active"
    assert count(arig, "audit_records") == 0


def test_reset_writes_exactly_one_audit_row(arig: Rig) -> None:
    sid = new_session(arig)
    assert arig.service.reset_session(sid) == Ok(None)
    rows = audit_rows(arig, sid)
    assert [(r.result_summary, r.timestamp, r.operator_role) for r in rows] == [
        ({"tool_name": "toolcall.reset_session", "status": "ok"}, START, "role-operations")
    ]
    assert arig.service.reset_session("sess-00000000000000ff").code == "SESSION_NOT_FOUND"
    assert len(audit_rows(arig, sid)) == 1 and count(arig, "audit_records") == 1


def test_reads_outside_a_turn_record_nothing(arig: Rig) -> None:
    sid = new_session(arig)
    ok(ask(arig, sid))
    before = count(arig, "audit_records")
    ok(arig.service.get_session(sid))
    assert count(arig, "audit_records") == before


class _RefusingAudit(SqliteAuditStore):
    """Returns a typed failure without the database ever raising (e.g. a remote audit sink)."""

    def append(self, entries):
        return Failure("PROVIDER_UNAVAILABLE", observed=("audit sink refused",))


class _FailsAfterWriting(SqliteSessionStore):
    """Writes through the real store, then returns a typed failure without the database raising."""

    def append_turn(self, *args, **kwargs):
        ok(super().append_turn(*args, **kwargs))
        return Failure("PROVIDER_UNAVAILABLE", observed=("failed after the write",))

    def reset(self, *args, **kwargs):
        ok(super().reset(*args, **kwargs))
        return Failure("PROVIDER_UNAVAILABLE", observed=("failed after the write",))


def test_a_store_failure_without_a_driver_error_rolls_back_what_it_already_wrote() -> None:
    rig = audited_rig()
    rig.service = SessionService(
        store=_FailsAfterWriting(rig.writer), clock=rig.clock, idgen=rig.idgen,
        pipeline=rig.pipeline, uow=rig.writer, audit=AuditWriter(rig.audit, rig.idgen),
        recorder=rig.recorder,
    )  # fmt: skip
    sid = new_session(rig)
    assert ask(rig, sid).code == "PROVIDER_UNAVAILABLE"
    assert rig.service.reset_session(sid).code == "PROVIDER_UNAVAILABLE"
    assert count(rig, "answers") == 0  # only tx.abort() can undo the answer the store inserted
    assert count(rig, "audit_records") == 0 and count(rig, "tool_calls") == 0
    stored = ok(rig.store.get(sid))
    assert stored.session.status == "active" and stored.session.context == empty_context()


def test_an_audit_failure_without_a_driver_error_still_rolls_back_the_answer() -> None:
    rig = audited_rig()
    rig.service = SessionService(
        store=rig.store, clock=rig.clock, idgen=rig.idgen, pipeline=rig.pipeline, uow=rig.writer,
        audit=AuditWriter(_RefusingAudit(rig.writer, 10_000), rig.idgen), recorder=rig.recorder,
    )  # fmt: skip
    sid = new_session(rig)
    assert ask(rig, sid).code == "AUDIT_WRITE_FAILED"
    assert rig.service.reset_session(sid).code == "AUDIT_WRITE_FAILED"
    assert count(rig, "answers") == 0  # only tx.abort() can undo the already-inserted answer
    stored = ok(rig.store.get(sid))
    assert stored.session.status == "active" and stored.session.context == empty_context()
