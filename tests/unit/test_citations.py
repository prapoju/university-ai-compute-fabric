"""Story 1.4 - the citation-binding guard (FR-13, AD-8, AD-14): every cited id is in the set."""

from __future__ import annotations

import pytest

from src.domain.citations import is_bound, unbound_citations
from src.domain.diagnosis import ClaimDraft, clock_entry, clock_read_from_entry
from src.dto import ClockReadDTO, EvidenceDTO

pytestmark = pytest.mark.unit


def evidence(*ids: str) -> list[EvidenceDTO]:
    return [
        EvidenceDTO(citation_id=cid, source_type=cid.partition("#")[0], snippet=cid, position=n)
        for n, cid in enumerate(ids)
    ]


def test_an_answer_whose_every_citation_is_in_the_evidence_is_bound() -> None:
    claims = [ClaimDraft("a", ("user#alex", "event#evt-4711")), ClaimDraft("b", ("user#alex",))]
    assert unbound_citations(claims, evidence("user#alex", "event#evt-4711", "clock#c")) == ()


def test_no_claims_is_trivially_bound() -> None:
    assert unbound_citations([], evidence("user#alex")) == ()


def test_a_cited_id_missing_from_the_evidence_is_returned() -> None:
    claims = [ClaimDraft("a", ("user#alex", "policy#ghost"))]
    assert unbound_citations(claims, evidence("user#alex")) == ("policy#ghost",)


def test_missing_ids_come_in_claim_order_and_only_once() -> None:
    claims = [
        ClaimDraft("a", ("job#j2", "user#alex", "job#j1")),
        ClaimDraft("b", ("job#j1", "job#j3", "job#j2")),
    ]
    assert unbound_citations(claims, evidence("user#alex")) == ("job#j2", "job#j1", "job#j3")


def test_the_match_is_exact_never_case_folded() -> None:
    # stored ids are canonical: a differently cased id is a different citation
    assert unbound_citations([ClaimDraft("a", ("user#Alex",))], evidence("user#alex")) == (
        "user#Alex",
    )


def test_a_duplicate_citation_id_in_the_evidence_is_returned_even_if_cited() -> None:
    claims = [ClaimDraft("a", ("user#alex",))]
    assert unbound_citations(claims, evidence("user#alex", "model#m", "user#alex")) == (
        "user#alex",
    )


def test_missing_ids_come_before_duplicates_and_nothing_repeats() -> None:
    claims = [ClaimDraft("a", ("policy#ghost", "model#m"))]
    found = unbound_citations(claims, evidence("model#m", "model#m", "user#u", "user#u", "user#u"))
    assert found == ("policy#ghost", "model#m", "user#u")


def test_is_bound_needs_every_claim_cited_and_every_citation_present() -> None:
    present = evidence("user#alex")
    assert is_bound([ClaimDraft("a", ("user#alex",))], present)
    assert is_bound([], present)
    assert not is_bound([ClaimDraft("a", ("policy#ghost",))], present)
    assert not is_bound([ClaimDraft("a", ("user#alex",))], evidence("user#alex", "user#alex"))


def test_a_claim_that_cites_nothing_is_not_bound() -> None:
    claims = [ClaimDraft("a", ("user#alex",)), ClaimDraft("uncited", ())]
    assert unbound_citations(claims, evidence("user#alex")) == ()  # no id to report
    assert not is_bound(claims, evidence("user#alex"))


# -- D4: a clock citation is rebuilt from its stored entry -------------------------------------
def test_a_clock_entry_round_trips_to_the_clock_read_it_was_built_from() -> None:
    read = ClockReadDTO(
        read_id="clk-0000000000000002", instant="2026-10-16T15:00:00.000Z", source="clock"
    )
    kind, cid, snippet = clock_entry(read)
    assert (kind, cid) == ("clock", "clock#clk-0000000000000002")
    assert clock_read_from_entry(cid, snippet) == read


@pytest.mark.parametrize(
    ("cid", "snippet"),
    [
        ("clock#clk-1", "clock read clk-2 at 2026-10-16T15:00:00.000Z"),  # names another read
        ("clock#clk-1", "clock read clk-1 at yesterday"),  # not an Instant
        ("clock#clk-1", "clock read clk-1 at 2026-13-40T15:00:00.000Z"),  # Instant-shaped, invalid
        ("clock#clk-1", "clock read clk-1 at 2026-10-16T15:00:00.000Z, trust me"),  # trailing text
        ("clock#clk-1", "user#alex: Alex Rivera, role student"),  # some other source's snippet
    ],
)
def test_a_snippet_that_is_not_exactly_a_clock_entry_rebuilds_nothing(
    cid: str, snippet: str
) -> None:
    assert clock_read_from_entry(cid, snippet) is None
