"""The schedule/window diagnoser (story 3.1, Annex 12.2): why a group's job cannot run now.

Order of a turn: extract the group -> resolve it exactly (AD-7) -> read the group's jobs and the
policy windows -> diagnose in the pure domain (AD-2) -> guarded prose, once (AD-8) -> mint claim
ids. An unknown group is a canonical outcome that never reaches the LLM; a missing or past
window is stated as such (contracts.md Q1, D55); any provider failure aborts the turn (AD-12) -
a window is never fabricated.
"""

from __future__ import annotations

from src.application.entity_resolver import EntityResolver, ResolvedGroup, Unresolved
from src.application.pipeline import TurnInput, TurnOutput
from src.application.turn_support import (
    canonical_turn,
    clarification_turn,
    mint_claims,
    write_prose,
)
from src.domain import canonical_strings as cs
from src.domain.result import Ok, Result, is_failure
from src.domain.window_diagnosis import diagnose_schedule_window, extract_group_reference
from src.dto import AnswerDTO, SelectorDTO
from src.ports.outbound import IdGenPort, JobsPort, LlmProsePort, WindowsPort

INTENT = "diagnose_schedule_window"


class WindowDiagnosisHandler:
    def __init__(
        self,
        *,
        resolver: EntityResolver,
        jobs: JobsPort,
        windows: WindowsPort,
        prose: LlmProsePort,
        idgen: IdGenPort,
    ) -> None:
        self._resolver = resolver
        self._jobs = jobs
        self._windows = windows
        self._prose = prose
        self._idgen = idgen

    def __call__(self, turn: TurnInput) -> Result[TurnOutput]:
        token = extract_group_reference(turn.query)
        if token is None:
            return Ok(clarification_turn(turn, cs.R_MISSING_GROUP))
        resolution = self._resolver.resolve_group(token)
        if is_failure(resolution):
            return resolution
        found = resolution.value
        if isinstance(found, Unresolved):
            message = cs.entity_not_found(found.refs)
            return Ok(canonical_turn(turn, INTENT, "ENTITY_NOT_FOUND", message))
        assert isinstance(found, ResolvedGroup)
        group = found.group

        jobs = self._jobs.select(SelectorDTO(method="filter", params={"group_id": group.id}))
        if is_failure(jobs):
            return jobs
        windows = self._windows.list()
        if is_failure(windows):
            return windows

        outcome = diagnose_schedule_window(group, jobs.value, windows.value, turn.now)
        prose = write_prose(self._prose, outcome.evidence, outcome.fact_tokens)
        if is_failure(prose):
            return prose
        claims = mint_claims(self._idgen, outcome.claims)
        if is_failure(claims):
            return claims
        chain = ["observation", "evidence", "diagnosis"]
        if outcome.next_open_window is not None:
            chain.append("recommendation")  # EXPERIENCE.md S2: the recommendation is the window
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=INTENT,
            answer_chain=chain,
            diagnosis_class=outcome.diagnosis_class,
            claims=claims.value,
            evidence=list(outcome.evidence),
            recommendation=outcome.recommendation,
            prose=prose.value,
        )
        return Ok(TurnOutput(answer, resolved_entities=(group.id,)))


__all__ = ["INTENT", "WindowDiagnosisHandler"]
