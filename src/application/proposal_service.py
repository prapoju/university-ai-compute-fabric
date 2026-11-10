"""Reading a proposal and re-dispatching a failed one (story 2.4, PD-6, AD-3; contracts L2).

``get_proposal`` is a read of the store. A re-dispatch checks the parent in the contract's order (it
exists, it is ``failed``, its snapshot had something to apply) and then runs a **new dry-run** from
the request, linked to the parent: the child has its own selector, snapshot and token and needs its
own confirmation, and the parent becomes ``superseded`` in the child's transaction unless it was
already partly applied. Nothing is applied here.
"""

from __future__ import annotations

from src.application.dry_run_service import DryRunService, Outcome
from src.domain.confirmation import has_actionable
from src.domain.error_catalog import fail
from src.domain.result import Result, is_failure
from src.dto import ProposalDTO
from src.ports.inbound import ProposalUseCases
from src.ports.outbound import ProposalStorePort


class ProposalService(ProposalUseCases):
    def __init__(self, *, proposals: ProposalStorePort, dry_run: DryRunService) -> None:
        self._proposals = proposals
        self._dry_run = dry_run

    def get_proposal(self, proposal_id: str) -> Result[ProposalDTO]:
        found = self._proposals.get(proposal_id)
        if is_failure(found):
            return found
        if found.value is None:
            return fail("PROPOSAL_NOT_FOUND", pid=proposal_id)
        return found

    def post_re_dispatch(
        self, parent_proposal_id: str, query_text: str, action: str, target_refs: list[str]
    ) -> Result[Outcome]:
        parent = self.get_proposal(parent_proposal_id)  # P3
        if is_failure(parent):
            return parent
        if parent.value.state != "failed":  # P1, P2: only a failed proposal is re-dispatched
            return fail(
                "PROPOSAL_STATE_INVALID",
                pid=parent_proposal_id,
                state=parent.value.state,
                action="re-dispatch",
            )
        if not has_actionable(parent.value.dry_run_snapshot.affected_items):  # P4
            return fail("DRY_RUN_EMPTY_SET")
        return self._dry_run.redispatch(parent.value, query_text, action, target_refs)
