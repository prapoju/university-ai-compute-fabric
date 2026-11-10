"""The citation-binding rule (FR-13, AD-8, AD-14): a claim may only cite its answer's evidence.

Pure and deterministic. The application ring applies it before any prose is written or any claim
id is minted, so an unbound answer downgrades to ``S_CNC`` instead of reaching the store, where
the ``claim_citations`` foreign key is only the physical backstop (story 1.4, D1).
"""

from __future__ import annotations

from collections.abc import Sequence

from src.domain.diagnosis import ClaimDraft
from src.dto import EvidenceDTO


def unbound_citations(
    claims: Sequence[ClaimDraft], evidence: Sequence[EvidenceDTO]
) -> tuple[str, ...]:
    """Every id that breaks the binding; empty when the answer is bound.

    First the cited ids absent from ``evidence`` (claim order), then any ``citation_id`` that
    appears more than once in ``evidence`` (position order). Ids match exactly, and none repeats.
    """
    present: set[str] = set()
    duplicated: list[str] = []
    for entry in evidence:
        if entry.citation_id in present and entry.citation_id not in duplicated:
            duplicated.append(entry.citation_id)
        present.add(entry.citation_id)
    found: list[str] = []
    for claim in claims:
        for cid in claim.citations:
            if cid not in present and cid not in found:
                found.append(cid)
    found.extend(cid for cid in duplicated if cid not in found)
    return tuple(found)


def is_bound(claims: Sequence[ClaimDraft], evidence: Sequence[EvidenceDTO]) -> bool:
    """Every claim cites at least one id and every id it cites is in ``evidence`` (AC 1).

    A claim that cites nothing has no id to report, so ``unbound_citations`` alone would call it
    bound; it is just as unbound and must never render.
    """
    return all(claim.citations for claim in claims) and not unbound_citations(claims, evidence)
