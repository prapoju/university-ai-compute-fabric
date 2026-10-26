"""Story 3.1 - pure window diagnosis and group reference extraction (Annex 12.2, FR-05)."""

from __future__ import annotations

import pytest

from src.domain.diagnosis import CannotConfirm
from src.domain.intent import Routed, classify
from src.domain.window_diagnosis import (
    NextOpenWindow,
    ScheduleDiagnosis,
    diagnose_schedule_window,
    extract_group_reference,
)
from src.dto import ClockReadDTO, PolicyWindowDTO, SelectorDTO

pytestmark = pytest.mark.unit

INTENT = "diagnose_schedule_window"


def clock(instant: str = "2026-10-16T15:00:00.000Z") -> ClockReadDTO:
    return ClockReadDTO(read_id="clk-0000000000000001", instant=instant, source="clock")


def inputs(providers, group_id: str = "group#group-4"):
    group = providers.groups.get(group_id).value
    jobs = providers.jobs.select(SelectorDTO(method="filter", params={"group_id": group_id})).value
    windows = providers.windows.list().value
    return group, jobs, windows


def diagnose(providers, instant: str = "2026-10-16T15:00:00.000Z", group_id="group#group-4"):
    group, jobs, windows = inputs(providers, group_id)
    return diagnose_schedule_window(group, jobs, windows, clock(instant))


# -- S2: Annex 12.2 -----------------------------------------------------------------------------
def test_s2_is_restricted_with_the_exact_next_window(providers) -> None:
    result = diagnose(providers)
    assert isinstance(result, ScheduleDiagnosis)
    assert result.diagnosis_class == "schedule_window_restricted"
    text = " ".join(claim.text for claim in result.claims)
    assert "2026-10-16T22:00:00.000Z" in text and "2026-10-17T06:00:00.000Z" in text
    assert "UTC" in text and "window#night" in text and "job#job-8823" in text


def test_s2_recommends_the_next_open_window_as_the_contract_shapes_it(providers) -> None:
    # contracts.md diagnose_schedule_window Q1: recommendation.next_open_window = {start, end, tz}
    result = diagnose(providers)
    window = NextOpenWindow("2026-10-16T22:00:00.000Z", "2026-10-17T06:00:00.000Z", "UTC")
    assert result.next_open_window == window
    assert result.recommendation == {
        "next_open_window": {
            "start": "2026-10-16T22:00:00.000Z", "end": "2026-10-17T06:00:00.000Z",
            "timezone": "UTC",
        }
    }  # fmt: skip


@pytest.mark.parametrize(
    ("instant", "group_id"),
    [
        ("2026-10-16T22:00:00.000Z", "group#group-4"),  # open now: no window starts after now
        ("2026-10-16T15:00:00.000Z", "group#group-7"),  # no constrained job: no window at all
    ],
)
def test_no_next_window_is_recommended_when_none_is_due(
    providers, instant: str, group_id: str
) -> None:
    result = diagnose(providers, instant, group_id=group_id)
    assert result.diagnosis_class == "schedule_no_constraint"
    assert result.next_open_window is None
    assert result.recommendation == {"next_open_window": None}


def test_evidence_is_group_job_window_then_the_clock_read(providers) -> None:
    result = diagnose(providers)
    assert [e.citation_id for e in result.evidence] == [
        "group#group-4", "job#job-8823", "window#night", "clock#clk-0000000000000001",
    ]  # fmt: skip
    assert [e.position for e in result.evidence] == [0, 1, 2, 3]


def test_every_claim_cites_group_job_window_and_clock_and_every_citation_resolves(
    providers,
) -> None:
    result = diagnose(providers)
    ids = {e.citation_id for e in result.evidence}
    assert len(result.claims) >= 2
    for claim in result.claims:
        assert set(claim.citations) == ids


# -- the half-open boundary and the clock --------------------------------------------------------
@pytest.mark.parametrize(
    ("instant", "restricted"),
    [
        ("2026-10-16T21:59:59.999Z", True),  # one millisecond before the window opens
        ("2026-10-16T22:00:00.000Z", False),  # start is inclusive: open
        ("2026-10-17T05:59:59.999Z", False),  # still open
    ],
)
def test_the_window_is_half_open_start_inclusive(providers, instant: str, restricted: bool) -> None:
    result = diagnose(providers, instant)
    assert isinstance(result, ScheduleDiagnosis)
    assert (result.diagnosis_class == "schedule_window_restricted") is restricted


def test_when_the_window_is_open_now_no_restriction_is_stated_and_none_is_rendered(
    providers,
) -> None:
    result = diagnose(providers, "2026-10-16T23:00:00.000Z")
    assert result.diagnosis_class == "schedule_no_constraint"
    assert "open now" in " ".join(claim.text for claim in result.claims)


def test_at_the_exclusive_end_there_is_no_later_window_so_it_cannot_confirm(providers) -> None:
    result = diagnose(providers, "2026-10-17T06:00:00.000Z")  # end is exclusive
    assert isinstance(result, CannotConfirm)
    assert result.checked[0] == "group#group-4"


def test_a_missing_window_record_is_cannot_confirm_never_a_fabricated_window(providers) -> None:
    group, jobs, _ = inputs(providers)
    result = diagnose_schedule_window(group, jobs, [], clock())
    assert isinstance(result, CannotConfirm)
    assert "window#night" in " ".join(result.checked)


def test_only_the_window_named_by_the_constraint_is_used(providers) -> None:
    group, jobs, windows = inputs(providers)
    other = PolicyWindowDTO(
        window_id="window#weekend", applies_to="fine-tuning",
        start="2026-10-17T00:00:00.000Z", end="2026-10-18T00:00:00.000Z", timezone="UTC",
    )  # fmt: skip
    result = diagnose_schedule_window(group, jobs, [other, *windows], clock())
    assert "window#night" in [e.citation_id for e in result.evidence]


# -- no scheduling constraint ------------------------------------------------------------------
def test_a_group_without_a_constrained_job_has_no_restriction_and_no_window(providers) -> None:
    result = diagnose(providers, group_id="group#group-7")  # its only live job is unconstrained
    assert isinstance(result, ScheduleDiagnosis)
    assert result.diagnosis_class == "schedule_no_constraint"
    assert "no scheduling constraint" in " ".join(c.text for c in result.claims).lower()
    assert not [e for e in result.evidence if e.source_type == "window"]


# -- the vocabulary prose must not carry -----------------------------------------------------------
def test_the_fact_tokens_cover_what_prose_must_not_say(providers) -> None:
    tokens = diagnose(providers).fact_tokens
    for expected in (
        "group#group-4", "group-4", "group 4", "job#job-8823", "job-8823", "window#night", "night",
        "2026-10-16", "22:00", "06:00", "clk-0000000000000001", "cs201",
    ):  # fmt: skip
        assert expected in tokens, expected


def test_the_same_inputs_give_identical_results(providers) -> None:
    assert diagnose(providers) == diagnose(providers)


# -- group reference extraction ----------------------------------------------------------------
@pytest.mark.parametrize(
    ("query", "ref"),
    [
        ("why can't group 4 run their fine-tuning job right now", "group-4"),
        ("Why can’t Group 4 run their fine-tuning job right now?", "group-4"),
        ("why is group-4's job pending", "group-4"),
        ("when can group 7 run its job", "group-7"),
        ("why won't group#group-4 start", "group#group-4"),
        ("why can't Group 99 run their job.", "group-99"),
    ],
)
def test_the_group_token_is_extracted(query: str, ref: str) -> None:
    assert extract_group_reference(query) == ref


@pytest.mark.parametrize(
    "query", ["why can't they run the job", "group", "", "why was alex denied"]
)
def test_no_group_means_no_reference(query: str) -> None:
    assert extract_group_reference(query) is None


# -- routing: >= 95% of 10 variants (AC 6) -----------------------------------------------------
VARIANTS = [
    "why can't group 4 run their fine-tuning job right now",
    "Why can’t Group 4 run their fine-tuning job right now?",
    "why cannot group 4 run its job",
    "why won't group 4's fine-tuning job start",
    "why is group 4's job not running",
    "why is group 4's job pending",
    "when can group 4 run their fine-tuning job",
    "why can't group-4 launch fine-tuning now",
    "why isn't group 4 able to run its job",
    "when does the next window open for group 4",
    "why is the fine-tuning job of group 4 waiting",
]


@pytest.mark.parametrize("query", VARIANTS)
def test_window_questions_route_to_the_schedule_intent(query: str) -> None:
    decision = classify(query, [])
    assert isinstance(decision, Routed) and decision.intent_code == INTENT


@pytest.mark.parametrize(
    "query",
    [
        "why was alex denied deepseek-coder",
        "why can't alex access deepseek-coder",
        "what's the weather?",
        "why was job 8823 rejected?",
    ],
)
def test_other_questions_do_not_route_to_the_schedule_intent(query: str) -> None:
    decision = classify(query, [])
    assert not (isinstance(decision, Routed) and decision.intent_code == INTENT)
