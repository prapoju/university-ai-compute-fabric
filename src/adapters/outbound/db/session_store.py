"""SQLite implementation of ``SessionStorePort`` over the migrated Module 12 schema.

Uses only the existing ``sessions`` and ``answers`` tables (a session's *turns* are its
``answers`` rows; there is no ``turns`` table). One lock serializes every statement on the shared
connection, so FastAPI's thread pool cannot interleave writes (single writer, AD-10); each
mutation is committed as one transaction, and any driver or data error becomes a typed
``Failure("PROVIDER_UNAVAILABLE")`` instead of an exception (AD-12).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from typing import TypeVar

from src.domain.result import Failure, Ok, Result
from src.dto import AnswerDTO, ClaimDTO, EvidenceDTO, SessionContextDTO, SessionDTO
from src.ports.outbound import SessionStorePort, StoredSession

T = TypeVar("T")

_SESSION_COLUMNS = (
    "session_id, created_at, operator_role, status, last_turn_at, "
    "context_resolved_entities, context_prior_intents, context_active_answer_ids"
)
_EMPTY_JSON = "[]"


class SqliteSessionStore(SessionStorePort):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = threading.RLock()
        # foreign keys are a per-connection setting: make sure answers cannot orphan
        with self._lock:
            try:
                self._connection.execute("PRAGMA foreign_keys = ON")
            except sqlite3.Error:
                pass  # a dead connection is reported by the first real call, as a Failure

    # -- helpers -------------------------------------------------------------------------------
    def _run(self, work: Callable[[], T]) -> Result[T]:
        with self._lock:
            try:
                value = work()
                if self._connection.in_transaction:
                    self._connection.commit()
                return Ok(value)
            except (sqlite3.Error, ValueError) as exc:  # ValueError: invalid stored JSON/DTO
                try:
                    if self._connection.in_transaction:
                        self._connection.rollback()
                except sqlite3.Error:
                    pass
                return Failure("PROVIDER_UNAVAILABLE", observed=(f"{type(exc).__name__}: {exc}",))

    @staticmethod
    def _context_json(context: SessionContextDTO) -> tuple[str, str, str]:
        return (
            json.dumps(context.resolved_entities),
            json.dumps(context.prior_intents),
            json.dumps(context.active_answer_ids),
        )

    # -- SessionStorePort ----------------------------------------------------------------------
    def create(self, session: SessionDTO, now: str) -> Result[None]:
        entities, intents, answers = self._context_json(session.context)

        def work() -> None:
            self._connection.execute(
                "INSERT INTO sessions (session_id, created_at, updated_at, operator_role, status,"
                " context_resolved_entities, context_prior_intents, context_active_answer_ids)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session.session_id,
                    session.created_at,
                    now,
                    session.operator_role,
                    session.status,
                    entities,
                    intents,
                    answers,
                ),
            )

        return self._run(work)

    def get(self, session_id: str) -> Result[StoredSession | None]:
        def work() -> StoredSession | None:
            row = self._connection.execute(
                f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row is None:
                return None
            sid, created_at, role, status, last_turn_at, entities, intents, answers = row
            context = SessionContextDTO(
                resolved_entities=json.loads(entities),
                prior_intents=json.loads(intents),
                active_answer_ids=json.loads(answers),
            )
            session = SessionDTO(
                session_id=sid,
                created_at=created_at,
                operator_role=role,
                context=context,
                status=status,
            )
            return StoredSession(session=session, last_turn_at=last_turn_at)

        return self._run(work)

    def list_turns(self, session_id: str) -> Result[list[AnswerDTO]]:
        def work() -> list[AnswerDTO]:
            rows = self._connection.execute(
                "SELECT answer_id, session_id, query, intent, answer_chain, diagnosis_class,"
                " canonical, recommendation, proposal_ref, prose FROM answers"
                " WHERE session_id = ? ORDER BY created_at, answer_id",
                (session_id,),
            ).fetchall()
            return [
                AnswerDTO(
                    answer_id=aid,
                    session_id=sid,
                    query=query,
                    intent=intent,
                    answer_chain=json.loads(chain),
                    diagnosis_class=diagnosis,
                    canonical=canonical,
                    claims=self._claims_of(aid),
                    evidence=self._evidence_of(aid),
                    recommendation=None if recommendation is None else json.loads(recommendation),
                    proposal_ref=proposal_ref,
                    prose=prose,
                )
                for (
                    aid, sid, query, intent, chain, diagnosis, canonical, recommendation,
                    proposal_ref, prose,
                ) in rows
            ]  # fmt: skip

        return self._run(work)

    def _evidence_of(self, answer_id: str) -> list[EvidenceDTO]:
        """The answer's evidence set in ``position`` order (AD-14). Caller holds the lock."""
        rows = self._connection.execute(
            "SELECT citation_id, source_type, snippet, position FROM evidence"
            " WHERE answer_id = ? ORDER BY position",
            (answer_id,),
        ).fetchall()
        return [
            EvidenceDTO(citation_id=cid, source_type=kind, snippet=snippet, position=position)
            for cid, kind, snippet, position in rows
        ]

    def _claims_of(self, answer_id: str) -> list[ClaimDTO]:
        """The answer's claims in id order, each with its citations in evidence order."""
        claims = self._connection.execute(
            "SELECT claim_id, text FROM claims WHERE answer_id = ? ORDER BY claim_id", (answer_id,)
        ).fetchall()
        cited = self._connection.execute(
            "SELECT cc.claim_id, cc.citation_id FROM claim_citations cc"
            " JOIN evidence e ON e.answer_id = cc.answer_id AND e.citation_id = cc.citation_id"
            " WHERE cc.answer_id = ? ORDER BY cc.claim_id, e.position",
            (answer_id,),
        ).fetchall()
        citations: dict[str, list[str]] = {}
        for claim_id, citation_id in cited:
            citations.setdefault(claim_id, []).append(citation_id)
        return [
            ClaimDTO(claim_id=claim_id, text=text, claim_citations=citations.get(claim_id, []))
            for claim_id, text in claims
        ]

    def append_turn(
        self, session_id: str, answer: AnswerDTO, context: SessionContextDTO, now: str
    ) -> Result[None]:
        entities, intents, answers = self._context_json(context)

        def work() -> None:
            self._connection.execute(
                "INSERT INTO answers (answer_id, session_id, query, intent, answer_chain,"
                " diagnosis_class, canonical, recommendation, proposal_ref, prose,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    answer.answer_id,
                    session_id,
                    answer.query,
                    answer.intent,
                    json.dumps(list(answer.answer_chain)),
                    answer.diagnosis_class,
                    answer.canonical,
                    None if answer.recommendation is None else json.dumps(answer.recommendation),
                    answer.proposal_ref,
                    answer.prose,
                    now,
                    now,
                ),
            )
            # evidence first: claim_citations reference (answer_id, citation_id) in it (AD-14)
            for entry in answer.evidence:
                self._connection.execute(
                    "INSERT INTO evidence (answer_id, citation_id, source_type, snippet, position,"
                    " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        answer.answer_id,
                        entry.citation_id,
                        entry.source_type,
                        entry.snippet,
                        entry.position,
                        now,
                    ),
                )
            for claim in answer.claims:
                self._connection.execute(
                    "INSERT INTO claims (claim_id, answer_id, text, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (claim.claim_id, answer.answer_id, claim.text, now),
                )
                for citation_id in claim.claim_citations:
                    self._connection.execute(
                        "INSERT INTO claim_citations (claim_id, answer_id, citation_id)"
                        " VALUES (?, ?, ?)",
                        (claim.claim_id, answer.answer_id, citation_id),
                    )
            updated = self._connection.execute(
                "UPDATE sessions SET context_resolved_entities = ?, context_prior_intents = ?,"
                " context_active_answer_ids = ?, last_turn_at = ?, updated_at = ?"
                " WHERE session_id = ?",
                (entities, intents, answers, now, now, session_id),
            )
            if updated.rowcount != 1:
                raise ValueError(f"unknown session {session_id}")

        return self._run(work)

    def mark_expired(self, session_id: str, now: str) -> Result[None]:
        def work() -> None:
            self._connection.execute(
                "UPDATE sessions SET status = 'expired', expired_at = coalesce(expired_at, ?),"
                " updated_at = ? WHERE session_id = ? AND status <> 'expired'",
                (now, now, session_id),
            )

        return self._run(work)

    def reset(self, session_id: str, now: str) -> Result[None]:
        def work() -> None:
            self._connection.execute(
                "UPDATE sessions SET status = 'reset', context_resolved_entities = ?,"
                " context_prior_intents = ?, context_active_answer_ids = ?, updated_at = ?"
                " WHERE session_id = ? AND status <> 'reset'",
                (_EMPTY_JSON, _EMPTY_JSON, _EMPTY_JSON, now, session_id),
            )

        return self._run(work)

    def applied_migrations(self) -> Result[set[str]]:
        """Filenames recorded in ``schema_migrations``, read under the store lock (readiness)."""

        def work() -> set[str]:
            rows = self._connection.execute("SELECT filename FROM schema_migrations").fetchall()
            return {name for (name,) in rows}

        return self._run(work)

    def highest_counters(self) -> Result[dict[str, int]]:
        def highest(table: str, column: str, prefix: str) -> int:
            rows = self._connection.execute(f"SELECT {column} FROM {table}").fetchall()
            return max((int(value[len(prefix) :], 16) for (value,) in rows), default=0)

        def work() -> dict[str, int]:
            return {
                "session": highest("sessions", "session_id", "sess-"),
                "answer": highest("answers", "answer_id", "ans-"),
                "claim": highest("claims", "claim_id", "clm-"),  # globally unique (PK)
            }

        return self._run(work)
