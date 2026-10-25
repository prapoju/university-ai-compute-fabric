"""Session use cases (contracts.md section 2) - the application ring behind the REST routes.

Enforces the contract preconditions in order, reads the clock once per call, writes only through
the session-store port and serializes the turns of one session so concurrent requests cannot lose
updates (NFR-6). Context never authorizes anything (AD-5): there is no destructive path here.
"""

from __future__ import annotations

import logging
import threading
import weakref

from src.application.pipeline import AnswerPipeline, TurnInput
from src.domain.error_catalog import fail
from src.domain.intent import classify
from src.domain.result import Failure, Ok, Result, is_failure
from src.domain.session_rules import (
    empty_context,
    is_idle_expired,
    is_valid_operator_role,
    normalise_query,
)
from src.dto import AnswerEnvelopeDTO, GetSessionResponse, SessionContextDTO, SessionDTO
from src.ports.inbound import CanonicalOutcome, SessionUseCases
from src.ports.outbound import ClockPort, IdGenPort, SessionStorePort, StoredSession

logger = logging.getLogger(__name__)


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
        # P1 first: a rejected query reads no clock and mints no id
        query = normalise_query(query_text)
        if is_failure(query):
            return query

        with self._guard(session_id):
            found = self._store.get(session_id)
            if is_failure(found):
                return found
            stored = found.value
            if stored is None:
                return fail("SESSION_NOT_FOUND", sid=session_id)

            # One clock read per request, taken inside the guard: turns of a session are then
            # stamped in the order they are committed, and an unknown session never needs a clock.
            now = self._clock.now()
            if is_failure(now):
                return now

            usable = self._is_usable(stored, now.value.instant)
            if is_failure(usable):
                return usable
            if not usable.value:  # P2: reset, expired or idle for more than 30 minutes
                persisted = self._store.mark_expired(session_id, now.value.instant)
                if is_failure(persisted):  # the 410 is true either way: do not hide it
                    logger.warning("could not persist expiry of %s: %s", session_id, persisted)
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
            used = list(dict.fromkeys(turn.resolved_entities))
            # Q2: the context only ever gains entities; a re-used one moves to the end so a
            # follow-up always sees the most recently used entity of each type.
            kept = [e for e in context.resolved_entities if e not in used]
            updated = SessionContextDTO(
                resolved_entities=[*kept, *used],
                prior_intents=[*context.prior_intents, turn.answer.intent],
                active_answer_ids=[*context.active_answer_ids, turn.answer.answer_id],
            )
            written = self._store.append_turn(session_id, turn.answer, updated, now.value.instant)
            if is_failure(written):
                return written
            return Ok(turn.canonical or AnswerEnvelopeDTO(answers=[turn.answer]))

    @staticmethod
    def _is_usable(stored: StoredSession, now: str) -> Result[bool]:
        if stored.session.status in ("reset", "expired"):
            return Ok(False)
        last_activity = stored.last_turn_at or stored.session.created_at
        try:
            return Ok(not is_idle_expired(last_activity, now))
        except ValueError as exc:  # a stored timestamp that is not a real instant
            observed = (f"stored timestamp is not a valid instant: {exc}",)
            return Failure("PROVIDER_UNAVAILABLE", observed=observed)

    # -- get_session ---------------------------------------------------------------------------
    def get_session(self, session_id: str) -> Result[GetSessionResponse]:
        # under the session guard so that context and turns come from one consistent snapshot
        with self._guard(session_id):
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
        with self._guard(session_id):
            found = self._store.get(session_id)
            if is_failure(found):
                return found
            if found.value is None:
                return fail("SESSION_NOT_FOUND", sid=session_id)
            now = self._clock.now()  # one read, inside the guard (see submit_query)
            if is_failure(now):
                return now
            return self._store.reset(session_id, now.value.instant)
