"""Pure node triage and runbook rendering (Annex 12.6, FR-07, FR-08, AD-9).

A runbook's steps are the registered template's steps, copied in template order and never
generated (AD-9). A node can be triaged only when it is cordoned and reports the queried code
(contracts.md ``diagnose_node_triage`` P1, P2); otherwise the canonical literal names the code the
node reports. Deterministic in its inputs (AD-2): no provider read, no clock, no id. The
application ring does the reads and mints the claim ids (R2).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.diagnosis import ClaimDraft, bare_id, clip, number_evidence
from src.dto import EvidenceDTO, NodeRecordDTO, RunbookTemplateDTO

NODE_TRIAGE_CLASS = "node_triage_runbook"


@dataclass(frozen=True)
class NodeTriageDiagnosis:
    diagnosis_class: str
    evidence: tuple[EvidenceDTO, ...]
    claims: tuple[ClaimDraft, ...]
    fact_tokens: frozenset[str]  # everything prose must not say (AD-8)
    recommendation: dict  # contracts.md ``recommendation.runbook``


def runbook_miss(node: NodeRecordDTO, queried: str) -> str | None:
    """The code the canonical literal names when ``node`` cannot be triaged for ``queried``.

    ``None`` when the node is cordoned and reports exactly the queried code. Otherwise the literal
    names the code the node reports, or the text ``null`` when it reports none (D43).
    """
    if node.cordoned and node.error_code == queried:
        return None
    return node.error_code or "null"


def is_renderable(template: RunbookTemplateDTO) -> bool:
    """A physical-intervention template renders only with an approved source (AD-9, D44)."""
    return not template.physical_intervention or bool(template.approved_source)


def runbook_recommendation(template: RunbookTemplateDTO) -> dict:
    """``recommendation.runbook``: steps and provenance as separate sections (AD-9)."""
    return {
        "runbook": {
            "steps": list(template.steps),
            "required_tools": list(template.required_tools),
            "safety_warnings": list(template.safety_warnings),
            "provenance": {"source": template.approved_source, "version": template.version},
        }
    }


def diagnose_node_triage(node: NodeRecordDTO, template: RunbookTemplateDTO) -> NodeTriageDiagnosis:
    """The node-triage diagnosis: one claim citing the node record, and the template's steps."""
    evidence = number_evidence([("node", node.id, clip(_node_snippet(node)))])
    claim = ClaimDraft(
        f"{node.hostname} ({node.id}) is cordoned and reports the error code {node.error_code}; "
        f"the registered runbook {template.template_id} applies to it.",
        tuple(e.citation_id for e in evidence),
    )
    tokens = {
        node.id,
        bare_id(node.id),
        node.hostname,
        node.error_code or "",
        template.template_id,
    }
    return NodeTriageDiagnosis(
        NODE_TRIAGE_CLASS,
        evidence,
        (claim,),
        frozenset(t.casefold() for t in tokens if t),
        runbook_recommendation(template),
    )


def _node_snippet(node: NodeRecordDTO) -> str:
    return (
        f"{node.id} hostname={node.hostname} status={node.status} "
        f"cordoned={str(node.cordoned).lower()} error_code={node.error_code} health={node.health}"
    )
