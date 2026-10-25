"""Session use cases (contracts.md section 2) - the application ring behind the REST routes.

Enforces the contract preconditions in order, reads the clock once per call, writes only through
the session-store port and serializes the turns of one session so concurrent requests cannot lose
updates (NFR-6). Context never authorizes anything (AD-5): there is no destructive path here.
"""

from __future__ import annotations

import threading
import weakref

from src.application.pipeline import AnswerPipeline, TurnInput
from src.domain.error_catalog import fail
from src.domain.intent import classify
from src.domain.result import Ok, Result, is_failure
from src.domain.session_rules import (
    empty_context,
    is_idle_expired,
    is_valid_operator_role,
    normalise_query,
)
from src.dto import AnswerEnvelopeDTO, GetSessionResponse, SessionContextDTO, SessionDTO
from src.ports.inbound import CanonicalOutcome, SessionUseCases
from src.ports.outbound import ClockPort, IdGenPort, SessionStorePort, StoredSession


class _Guard:
    """A per-session lock that can be held weakly (a bare ``threading.Lock`` cannot)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __enter__(self) -> None:
        self._lock.acquire()

    def __exit__(self, *_: object) -> None:
        self._lock.release()


class SessionService(SessionUseCases):
    def __init__(
        self,
        *,
        store: SessionStorePort,
        clock: ClockPort,
        idgen: IdGenPort,
        pipeline: AnswerPipeline,
    ) -> None:
        self._store = store
        self._clock = clock
        self._idgen = idgen
        self._pipeline = pipeline
        self._guards: weakref.WeakValueDictionary[str, _Guard] = weakref.WeakValueDictionary()
        self._registry_lock = threading.Lock()

    def _guard(self, session_id: str) -> _Guard:
        with self._registry_lock:
            guard = self._guards.get(session_id)
            if guard is None:
                guard = _Guard()
                self._guards[session_id] = guard
            return guard

    # -- create_session ------------------------------------------------------------------------
    def create_session(self, operator_role: str) -> Result[SessionDTO]:
        if not is_valid_operator_role(operator_role):
            return fail("VALIDATION_MALFORMED_BODY", schema_id="CreateSessionRequest")
        now = self._clock.now()
        if is_failure(now):
            return now
        session_id = self._idgen.new_id("session")
        if is_failure(session_id):
            return session_id
        session = SessionDTO(
            session_id=session_id.value,
            created_at=now.value.instant,
            operator_role=operator_role,
            context=empty_context(),
            status="active",
        )
        stored = self._store.create(session, now.value.instant)
        return stored if is_failure(stored) else Ok(session)

    # -- submit_query --------------------------------------------------------------------------
    def submit_query(
        self, session_id: str, query_text: str
    ) -> Result[AnswerEnvelopeDTO | CanonicalOutcome]:
        query = normalise_query(
            query_text
        )  # P1 first: a rejected query reads no clock, mints no id
        if is_failure(query):
            return query
        now = self._clock.now()  # one read for the whole turn
        if is_failure(now):
            return now

        with self._guard(session_id):
            found = self._store.get(session_id)
            if is_failure(found):
                return found
            stored = found.value
            if stored is None:
                return fail("SESSION_NOT_FOUND", sid=session_id)

            if self._is_unusable(stored, now.value.instant):  # P2: reset, expired or idle
                persisted = self._store.mark_expired(session_id, now.value.instant)
                if is_failure(persisted):
                    return persisted
                return fail("SESSION_EXPIRED", sid=session_id)

            answer_id = self._idgen.new_id("answer")
            if is_failure(answer_id):
                return answer_id
            context = stored.session.context
            output = self._pipeline.respond(
                TurnInput(
                    session_id=session_id,
                    answer_id=answer_id.value,
                    query=query.value,
                    now=now.value,
                    decision=classify(query.value, context.prior_intents),
                    context=context,
                )
            )
            if is_failure(output):
                return output

            turn = output.value
            new_entities = [e for e in turn.resolved_entities if e not in context.resolved_entities]
            updated = SessionContextDTO(
                resolved_entities=[*context.resolved_entities, *new_entities],
                prior_intents=[*context.prior_intents, turn.answer.intent],
                active_answer_ids=[*context.active_answer_ids, turn.answer.answer_id],
            )
            written = self._store.append_turn(session_id, turn.answer, updated, now.value.instant)
            if is_failure(written):
                return written
            return Ok(turn.canonical or AnswerEnvelopeDTO(answers=[turn.answer]))

    @staticmethod
    def _is_unusable(stored: StoredSession, now: str) -> bool:
        if stored.session.status in ("reset", "expired"):
            return True
        last_activity = stored.last_turn_at or stored.session.created_at
        return is_idle_expired(last_activity, now)

    # -- get_session ---------------------------------------------------------------------------
    def get_session(self, session_id: str) -> Result[GetSessionResponse]:
        found = self._store.get(session_id)
        if is_failure(found):
            return found
        if found.value is None:
            return fail("SESSION_NOT_FOUND", sid=session_id)
        turns = self._store.list_turns(session_id)
        if is_failure(turns):
            return turns
        session = found.value.session
        return Ok(
            GetSessionResponse(
                session_id=session.session_id,
                created_at=session.created_at,
                operator_role=session.operator_role,
                context=session.context,
                status=session.status,
                turns=turns.value,
            )
        )

    # -- reset_session -------------------------------------------------------------------------
    def reset_session(self, session_id: str) -> Result[None]:
        now = self._clock.now()
        if is_failure(now):
            return now
        with self._guard(session_id):
            found = self._store.get(session_id)
            if is_failure(found):
                return found
            if found.value is None:
                return fail("SESSION_NOT_FOUND", sid=session_id)
            return self._store.reset(session_id, now.value.instant)
