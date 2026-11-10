"""The chat use case (story 2.2, Annex 12.4, D8): refusal first, then the dry-run.

Two steps, each atomic on its own. The refusal turn of story 2.1 is stored first. Only when that
outcome is ``ACTION_REFUSED`` is the destructive request read again with the same pure parser the
refusal handler used, and handed to the dry-run use case. Any other outcome is returned untouched,
and a failed dry-run is returned as that typed failure with the refusal turn still recorded.
"""

from __future__ import annotations

from src.domain.intent import normalise_query
from src.domain.result import Ok, Result, is_failure
from src.domain.safety import DestructiveRequest, parse_destructive
from src.dto import AnswerEnvelopeDTO
from src.ports.inbound import (
    CanonicalOutcome,
    ChatRefusal,
    ChatUseCases,
    DestructiveUseCases,
    SessionUseCases,
)

REFUSED = "ACTION_REFUSED"


class ChatService(ChatUseCases):
    def __init__(self, *, sessions: SessionUseCases, destructive: DestructiveUseCases) -> None:
        self._sessions = sessions
        self._destructive = destructive

    def chat(
        self, operator_role: str, query: str
    ) -> Result[AnswerEnvelopeDTO | CanonicalOutcome | ChatRefusal]:
        created = self._sessions.create_session(operator_role)
        if is_failure(created):
            return created
        session_id = created.value.session_id
        submitted = self._sessions.submit_query(session_id, query)
        if is_failure(submitted):
            return submitted
        outcome = submitted.value
        if not (isinstance(outcome, CanonicalOutcome) and outcome.code == REFUSED):
            return submitted

        request = parse_destructive(normalise_query(query.strip()))
        if not isinstance(request, DestructiveRequest):  # refused, so a request is there; stay safe
            return submitted
        dry_run = self._destructive.dry_run_request(session_id, request)
        if is_failure(dry_run):
            return dry_run  # the refusal turn stays recorded (D8)
        if isinstance(dry_run.value, CanonicalOutcome):
            return dry_run
        return Ok(ChatRefusal(refusal=outcome, dry_run=dry_run.value))
