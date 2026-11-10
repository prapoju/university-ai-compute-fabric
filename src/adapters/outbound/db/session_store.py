"""SQLite implementation of ``SessionStorePort`` over the migrated Module 12 schema.

Uses only the existing ``sessions`` and ``answers`` tables (a session's *turns* are its
``answers`` rows; there is no ``turns`` table). Every statement goes through the one
``SqliteWriter`` (review D-6, single writer, AD-10): a mutation runs in ``writer.transaction()``,
so it joins a unit of work the application already opened, and a read runs under
``writer.read()``. Any driver or data error becomes a typed ``Failure("PROVIDER_UNAVAILABLE")``
instead of an exception (AD-12).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import TypeVar

from src.adapters.outbound.db.sqlite_writer import SqliteWriter
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
    def __init__(self, writer: SqliteWriter) -> None:
        self._writer = writer

    # -- helpers -------------------------------------------------------------------------------
    def _run(self, work: Callable[[sqlite3.Connection], T], *, write: bool = False) -> Result[T]:
        """``work`` inside a writer transaction (``write``) or under the writer's read lock.

        Any other exception propagates; the writer has already rolled the transaction back, so no
        half-written turn can be committed by a later write.
        """
        scope = self._writer.transaction if write else self._writer.read
        try:
            with scope() as connection:
                return Ok(work(connection))
        except (sqlite3.Error, ValueError) as exc:  # ValueError: invalid stored JSON/DTO
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

        def work(db: sqlite3.Connection) -> None:
            db.execute(
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

        return self._run(work, write=True)

    def get(self, session_id: str) -> Result[StoredSession | None]:
        def work(db: sqlite3.Connection) -> StoredSession | None:
            row = db.execute(
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
        def work(db: sqlite3.Connection) -> list[AnswerDTO]:
            rows = db.execute(
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
                    claims=self._claims_of(db, aid),
                    evidence=self._evidence_of(db, aid),
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

    @staticmethod
    def _evidence_of(db: sqlite3.Connection, answer_id: str) -> list[EvidenceDTO]:
        """The answer's evidence set in ``position`` order (AD-14). Caller holds the writer lock."""
        rows = db.execute(
            "SELECT citation_id, source_type, snippet, position FROM evidence"
            " WHERE answer_id = ? ORDER BY position",
            (answer_id,),
        ).fetchall()
        return [
            EvidenceDTO(citation_id=cid, source_type=kind, snippet=snippet, position=position)
            for cid, kind, snippet, position in rows
        ]

    @staticmethod
    def _claims_of(db: sqlite3.Connection, answer_id: str) -> list[ClaimDTO]:
        """The answer's claims in id order, each with its citations in evidence order."""
        claims = db.execute(
            "SELECT claim_id, text FROM claims WHERE answer_id = ? ORDER BY claim_id", (answer_id,)
        ).fetchall()
        cited = db.execute(
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

    def answer_evidence(self, answer_id: str) -> Result[list[EvidenceDTO] | None]:
        def work(db: sqlite3.Connection) -> list[EvidenceDTO] | None:
            row = db.execute(
                "SELECT 1 FROM answers WHERE answer_id = ?", (answer_id,)
            ).fetchone()
            return None if row is None else self._evidence_of(db, answer_id)

        return self._run(work)

    def cited_snippet(self, citation_id: str) -> Result[str | None]:
        def work(db: sqlite3.Connection) -> str | None:
            row = db.execute(
                "SELECT snippet FROM evidence WHERE citation_id = ?"
                " ORDER BY created_at DESC, answer_id DESC LIMIT 1",
                (citation_id,),
            ).fetchone()
            return None if row is None else row[0]

        return self._run(work)

    def append_turn(
        self, session_id: str, answer: AnswerDTO, context: SessionContextDTO, now: str
    ) -> Result[None]:
        entities, intents, answers = self._context_json(context)

        def work(db: sqlite3.Connection) -> None:
            db.execute(
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
                db.execute(
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
                db.execute(
                    "INSERT INTO claims (claim_id, answer_id, text, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (claim.claim_id, answer.answer_id, claim.text, now),
                )
                for citation_id in claim.claim_citations:
                    db.execute(
                        "INSERT INTO claim_citations (claim_id, answer_id, citation_id)"
                        " VALUES (?, ?, ?)",
                        (claim.claim_id, answer.answer_id, citation_id),
                    )
            updated = db.execute(
                "UPDATE sessions SET context_resolved_entities = ?, context_prior_intents = ?,"
                " context_active_answer_ids = ?, last_turn_at = ?, updated_at = ?"
                " WHERE session_id = ?",
                (entities, intents, answers, now, now, session_id),
            )
            if updated.rowcount != 1:
                raise ValueError(f"unknown session {session_id}")

        return self._run(work, write=True)

    def mark_expired(self, session_id: str, now: str) -> Result[None]:
        def work(db: sqlite3.Connection) -> None:
            db.execute(
                "UPDATE sessions SET status = 'expired', expired_at = coalesce(expired_at, ?),"
                " updated_at = ? WHERE session_id = ? AND status <> 'expired'",
                (now, now, session_id),
            )

        return self._run(work, write=True)

    def reset(self, session_id: str, now: str) -> Result[None]:
        def work(db: sqlite3.Connection) -> None:
            db.execute(
                "UPDATE sessions SET status = 'reset', context_resolved_entities = ?,"
                " context_prior_intents = ?, context_active_answer_ids = ?, updated_at = ?"
                " WHERE session_id = ? AND status <> 'reset'",
                (_EMPTY_JSON, _EMPTY_JSON, _EMPTY_JSON, now, session_id),
            )

        return self._run(work, write=True)

    def applied_migrations(self) -> Result[set[str]]:
        """Filenames recorded in ``schema_migrations``, read under the writer lock (readiness)."""

        def work(db: sqlite3.Connection) -> set[str]:
            rows = db.execute("SELECT filename FROM schema_migrations").fetchall()
            return {name for (name,) in rows}

        return self._run(work)

    def highest_counters(self) -> Result[dict[str, int]]:
        def highest(db: sqlite3.Connection, table: str, column: str, prefix: str) -> int:
            rows = db.execute(f"SELECT {column} FROM {table}").fetchall()
            return max((int(value[len(prefix) :], 16) for (value,) in rows), default=0)

        def work(db: sqlite3.Connection) -> dict[str, int]:
            return {
                "session": highest(db, "sessions", "session_id", "sess-"),
                "answer": highest(db, "answers", "answer_id", "ans-"),
                "claim": highest(db, "claims", "claim_id", "clm-"),  # globally unique (PK)
            }

        return self._run(work)
