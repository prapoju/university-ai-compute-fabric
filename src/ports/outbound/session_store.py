"""Internal port for the Module-12-OWNED session and answer store.

Not a provider port: the contracts define no port for Module 12's own persistence, but the
hexagonal rules (ports-and-adapters.md R3) keep the application ring free of any DB driver, so it
talks to this interface and a SQLite adapter implements it. AD-1 (read-only) protects the
operational *estate*; Module-12-owned stores are the only writable stores (ARCHITECTURE
"Consistency Conventions"). Every operation returns a typed ``Result`` (AD-12).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.result import Result
from src.dto import AnswerDTO, SessionContextDTO, SessionDTO


@dataclass(frozen=True)
class StoredSession:
    """A stored session plus the activity timestamp the idle rule needs."""

    session: SessionDTO
    last_turn_at: str | None


class SessionStorePort(ABC):
    @abstractmethod
    def create(self, session: SessionDTO, now: str) -> Result[None]:
        """Insert a new session (``session_id`` is unique)."""

    @abstractmethod
    def get(self, session_id: str) -> Result[StoredSession | None]:
        """The stored session; a miss is ``Ok(None)``."""

    @abstractmethod
    def list_turns(self, session_id: str) -> Result[list[AnswerDTO]]:
        """The session's answers (its turns) in creation order."""

    @abstractmethod
    def append_turn(
        self, session_id: str, answer: AnswerDTO, context: SessionContextDTO, now: str
    ) -> Result[None]:
        """Store ``answer`` and replace the session context, atomically.

        Either both are written or neither is, so no orphan answer or half-updated context.
        """

    @abstractmethod
    def mark_expired(self, session_id: str, now: str) -> Result[None]:
        """Persist ``status = expired`` (idempotent)."""

    @abstractmethod
    def reset(self, session_id: str, now: str) -> Result[None]:
        """Clear the context and set ``status = reset`` (idempotent); keeps the turns."""

    @abstractmethod
    def highest_counters(self) -> Result[dict[str, int]]:
        """Highest numeric suffix per id kind (``session``, ``answer``) already stored.

        Used to seed the id generator so a restart never reissues a persisted id.
        """
