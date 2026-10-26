"""Pure schedule/window diagnosis (Annex 12.2, FR-05): why a group's job cannot run now.

Deterministic in its inputs (AD-2): the class, claims, citations, evidence order and the
recommended next open window never depend on an LLM or on a clock read inside this module. A
job's ``scheduling_constraint`` names the policy window that governs it (``night`` ->
``window#night``); the window is half-open ``[start, end)``. The application ring does the
provider reads and mints the claim ids (R2).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from src.domain.diagnosis import (
    ClaimDraft,
    bare_id,
    clip,
    clock_entry,
    number_evidence,
)
from src.domain.instants import parse_instant
from src.domain.references import clean_query, strip_token
from src.dto import (
    ClockReadDTO,
    EvidenceDTO,
    GroupRecordDTO,
    JobRecordDTO,
    PolicyWindowDTO,
)

_ACTIVE = ("pending", "running")  # a finished or cancelled job is not waiting for a window

_TYPED_GROUP = re.compile(r"\bgroup#(?P<ref>[^\s,;:?!()\[\]]+)", re.I)
_NAMED_GROUP = re.compile(r"\bgroup[\s-]+(?P<ref>[a-z0-9][^\s,;:?!()\[\]]*)", re.I)


@dataclass(frozen=True)
class NextOpenWindow:
    """``recommendation.next_open_window`` of contracts.md ``diagnose_schedule_window`` Q1."""

    start: str
    end: str
    timezone: str


@dataclass(frozen=True)
class ScheduleDiagnosis:
    diagnosis_class: str  # schedule_window_restricted | schedule_no_constraint
    evidence: tuple[EvidenceDTO, ...]
    claims: tuple[ClaimDraft, ...]
    fact_tokens: frozenset[str]  # everything prose must not say (AD-8)
    next_open_window: NextOpenWindow | None = None  # only a window that starts after now (D55)

    @property
    def recommendation(self) -> dict[str, dict[str, str] | None]:
        """The contract's recommendation object: the next open window, or null when none is due."""
        window = self.next_open_window
        return {"next_open_window": None if window is None else asdict(window)}


def extract_group_reference(query: str) -> str | None:
    """The raw group token of the query: ``group-4`` for ``group 4``, ``group#group-4`` as typed."""
    text = clean_query(query)
    typed = _TYPED_GROUP.search(text)
    if typed is not None:
        ref = strip_token(typed["ref"])
        return f"group#{ref}" if ref else None
    named = _NAMED_GROUP.search(text)
    if named is None:
        return None
    ref = strip_token(named["ref"])
    return f"group-{ref}" if ref else None


def diagnose_schedule_window(
    group: GroupRecordDTO,
    jobs: Sequence[JobRecordDTO],
    windows: Sequence[PolicyWindowDTO],
    clock: ClockReadDTO,
) -> ScheduleDiagnosis:
    """Why the group's constrained job cannot run at ``clock`` and when the window next opens."""
    waiting = sorted(
        (
            j
            for j in jobs
            if j.group_id == group.id and j.status in _ACTIVE and j.scheduling_constraint
        ),
        key=lambda j: j.id,
    )
    if not waiting:
        return _no_constraint(group, clock)

    job = waiting[0]
    window_id = f"window#{job.scheduling_constraint}"
    window = next((w for w in windows if w.window_id == window_id), None)
    gathered = [
        ("group", group.id, clip(_group_snippet(group))),
        ("job", job.id, clip(_job_snippet(job))),
    ]
    if window is None:  # contracts.md Q1 (D55): an empty window set restricts nothing
        return _no_window_on_record(group, job, window_id, clock, gathered)

    now = parse_instant(clock.instant)
    start, end = parse_instant(window.start), parse_instant(window.end)
    evidence = number_evidence(
        [*gathered, ("window", window.window_id, clip(_window_snippet(window))), clock_entry(clock)]
    )
    cites = tuple(e.citation_id for e in evidence)
    where = f"{window.start} to {window.end} ({window.timezone})"
    tokens = _tokens(group, job, window, clock)
    if start <= now < end:
        claim = ClaimDraft(
            f"The window {window.window_id} for {window.applies_to} is open now ({where}) at "
            f"the clock read {clock.read_id} ({clock.instant}); no window restriction blocks "
            f"{job.id}.",
            cites,
        )
        return ScheduleDiagnosis("schedule_no_constraint", evidence, (claim,), tokens)
    constrained = ClaimDraft(
        f"{group.name} ({group.id}) has the {job.status} job {job.id} for {job.course} "
        f"constrained to the {job.scheduling_constraint} window {window.window_id}.",
        cites,
    )
    if now >= end:  # the only window on record is over: say so, never invent a later one (D55)
        claims = (
            constrained,
            ClaimDraft(
                f"{window.window_id} permits {window.applies_to} only from {where}; the clock "
                f"read {clock.read_id} is {clock.instant}, at or after its end, so {job.id} "
                f"cannot run now.",
                cites,
            ),
            ClaimDraft(
                f"No later {window.window_id} is on record, so no next open window can be given.",
                cites,
            ),
        )
        return ScheduleDiagnosis("schedule_window_restricted", evidence, claims, tokens)
    claims = (
        constrained,
        ClaimDraft(
            f"{window.window_id} permits {window.applies_to} only from {where}; the clock read "
            f"{clock.read_id} is {clock.instant}, outside it, so {job.id} cannot run now.",
            cites,
        ),
        ClaimDraft(
            f"The next open window starts {window.start} and ends {window.end} "
            f"({window.timezone}).",
            cites,
        ),
    )
    upcoming = NextOpenWindow(window.start, window.end, window.timezone)
    return ScheduleDiagnosis("schedule_window_restricted", evidence, claims, tokens, upcoming)


def _no_constraint(group: GroupRecordDTO, clock: ClockReadDTO) -> ScheduleDiagnosis:
    evidence = number_evidence(
        [("group", group.id, clip(_group_snippet(group))), clock_entry(clock)]
    )
    claim = ClaimDraft(
        f"No scheduling constraint applies to the jobs of {group.name} ({group.id}) at the "
        f"clock read {clock.read_id}; no window restriction is in effect.",
        tuple(e.citation_id for e in evidence),
    )
    tokens = {group.id, bare_id(group.id), group.name, clock.read_id, clock.instant}
    return ScheduleDiagnosis(
        "schedule_no_constraint", evidence, (claim,), frozenset(t.casefold() for t in tokens)
    )


def _no_window_on_record(
    group: GroupRecordDTO,
    job: JobRecordDTO,
    window_id: str,
    clock: ClockReadDTO,
    gathered: list[tuple[str, str, str]],
) -> ScheduleDiagnosis:
    evidence = number_evidence([*gathered, clock_entry(clock)])
    claim = ClaimDraft(
        f"{group.name} ({group.id}) has the {job.status} job {job.id} constrained to the "
        f"{job.scheduling_constraint} window, but no {window_id} is on record at the clock read "
        f"{clock.read_id}; no window restriction can be stated and no window is given.",
        tuple(e.citation_id for e in evidence),
    )
    tokens = {
        group.id, bare_id(group.id), group.name,
        job.id, bare_id(job.id), job.course, str(job.scheduling_constraint),
        window_id, bare_id(window_id), clock.read_id, clock.instant,
    }  # fmt: skip
    return ScheduleDiagnosis(
        "schedule_no_constraint", evidence, (claim,), frozenset(t.casefold() for t in tokens)
    )


# -- evidence snippets and the guarded vocabulary --------------------------------------------------
def _group_snippet(group: GroupRecordDTO) -> str:
    return f"{group.id}: {group.name}, members {', '.join(group.members)}"


def _job_snippet(job: JobRecordDTO) -> str:
    return (
        f"{job.id}: course {job.course}, status {job.status}, "
        f"scheduling constraint {job.scheduling_constraint}"
    )


def _window_snippet(window: PolicyWindowDTO) -> str:
    return (
        f"{window.window_id}: applies to {window.applies_to}, "
        f"{window.start} to {window.end} ({window.timezone})"
    )


def _tokens(
    group: GroupRecordDTO, job: JobRecordDTO, window: PolicyWindowDTO, clock: ClockReadDTO
) -> frozenset[str]:
    tokens = {
        group.id, bare_id(group.id), group.name,
        job.id, bare_id(job.id), job.course, str(job.scheduling_constraint),
        window.window_id, bare_id(window.window_id), window.applies_to, window.timezone,
        window.start, window.end, window.start[:10], window.end[:10],
        window.start[11:19], window.end[11:19], window.start[11:16], window.end[11:16],
        clock.read_id, clock.instant, clock.instant[:10], clock.instant[11:19],
    }  # fmt: skip
    return frozenset(t.casefold() for t in tokens if t)
