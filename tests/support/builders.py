"""Row/record factories used by every suite.

Read-port records follow ``contracts.md`` §0.3 *verbatim* ("extra fields are a
contract violation"); Module-12-owned rows follow
``planning/detailed-design/schemas/001_module12_copilot_schema.sql`` CHECKs.

All values are deterministic: ids come from `IdFactory`, timestamps from a supplied
`Instant` string (usually ``fake_clock.current``).
"""

from __future__ import annotations

from typing import Any

from support.ids import IdFactory

DEFAULT_INSTANT = "2026-10-16T15:00:00.000Z"


class SampleData:
    """Builds schema-valid rows and contract-exact records."""

    def __init__(self, ids: IdFactory | None = None, now: str = DEFAULT_INSTANT) -> None:
        self.ids = ids or IdFactory()
        self.now = now

    def at(self, instant: str | None = None) -> str:
        return instant or self.now

    # -- Module-12-owned rows (SQLite tables) ------------------------------
    def session_row(
        self,
        *,
        session_id: str | None = None,
        operator_role: str | None = None,
        status: str = "active",
        created_at: str | None = None,
        last_turn_at: str | None = None,
        expired_at: str | None = None,
        resolved: list[str] | None = None,
        prior_intents: list[str] | None = None,
        active_answer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        import json

        ts = self.at(created_at)
        return {
            "session_id": session_id or self.ids.session_id(),
            "created_at": ts,
            "updated_at": ts,
            "last_turn_at": last_turn_at,
            "operator_role": operator_role or "role-operations",
            "status": status,
            "expired_at": expired_at or (ts if status == "expired" else None),
            "context_resolved_entities": json.dumps(resolved or []),
            "context_prior_intents": json.dumps(prior_intents or []),
            "context_active_answer_ids": json.dumps(active_answer_ids or []),
        }

    def answer_row(
        self,
        *,
        session_id: str,
        answer_id: str | None = None,
        query: str = "why was job 8823 cancelled?",
        intent: str = "diagnose_retrospective",
        answer_chain: list[str] | None = None,
        diagnosis_class: str | None = None,
        canonical: str | None = None,
        recommendation: dict[str, Any] | None = None,
        proposal_ref: str | None = None,
        prose: str = "",
        created_at: str | None = None,
    ) -> dict[str, Any]:
        import json

        ts = self.at(created_at)
        return {
            "answer_id": answer_id or self.ids.answer_id(),
            "session_id": session_id,
            "query": query,
            "intent": intent,
            "answer_chain": json.dumps(answer_chain or ["observation", "evidence"]),
            "diagnosis_class": diagnosis_class,
            "canonical": canonical,
            "recommendation": None if recommendation is None else json.dumps(recommendation),
            "proposal_ref": proposal_ref,
            "prose": prose,
            "created_at": ts,
            "updated_at": ts,
        }

    def evidence_row(
        self,
        *,
        answer_id: str,
        citation_id: str = "node#ws-gpu-11",
        source_type: str = "node",
        snippet: str = "ws-gpu-11 is cordoned with ERR_THERMAL_88.",
        position: int = 0,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        return {
            "answer_id": answer_id,
            "citation_id": citation_id,
            "source_type": source_type,
            "snippet": snippet,
            "position": position,
            "created_at": self.at(created_at),
        }

    def claim_row(
        self,
        *,
        answer_id: str,
        claim_id: str | None = None,
        text: str = "Node ws-gpu-11 is cordoned.",
        created_at: str | None = None,
    ) -> dict[str, Any]:
        return {
            "claim_id": claim_id or self.ids.claim_id(),
            "answer_id": answer_id,
            "text": text,
            "created_at": self.at(created_at),
        }

    def claim_citation_row(self, *, claim_id: str, answer_id: str, citation_id: str) -> dict[str, Any]:
        return {"claim_id": claim_id, "answer_id": answer_id, "citation_id": citation_id}

    def tool_call_row(
        self,
        *,
        session_id: str,
        tool_call_id: str | None = None,
        tool_name: str = "toolcall.answer_query",
        params_summary: dict[str, Any] | None = None,
        timestamp: str | None = None,
        status: str = "ok",
    ) -> dict[str, Any]:
        import json

        ts = self.at(timestamp)
        return {
            "tool_call_id": tool_call_id or self.ids.tool_call_id(),
            "session_id": session_id,
            "tool_name": tool_name,
            "params_summary": json.dumps(params_summary or {}),
            "timestamp": ts,
            "status": status,
            "created_at": ts,
        }

    def proposal_row(
        self,
        *,
        session_id: str,
        proposal_id: str | None = None,
        state: str = "dry_run",
        action: str = "cordon_node",
        selector: dict[str, Any] | None = None,
        affected_items: list[dict[str, Any]] | None = None,
        gate_token: str | None = None,
        snapshot_timestamp: str | None = None,
        supersedes_proposal_id: str | None = None,
        confirmed_at: str | None = None,
        executor_status: str | None = None,
        applied_records: list[str] | None = None,
        executor_timestamp: str | None = None,
    ) -> dict[str, Any]:
        import json

        ts = self.at(snapshot_timestamp)
        # a `fault` node is a plausible default target; shape mirrors DryRunSnapshot
        items = affected_items if affected_items is not None else [
            {
                "key": "node#ws-gpu-11",
                "actionable": True,
                "actionable_field": "cordoned",
                "actionable_value": "true",
            }
        ]
        row: dict[str, Any] = {
            "proposal_id": proposal_id or self.ids.proposal_id(),
            "session_id": session_id,
            "state": state,
            "action": action,
            "supersedes_proposal_id": supersedes_proposal_id,
            "selector": json.dumps(selector or {"method": "nodes_port.select",
                                                "params": {"node_ids": ["node#ws-gpu-11"]}}),
            "affected_items": json.dumps(items),
            "snapshot_timestamp": ts,
            "gate_token": gate_token or self.ids.gate_token(),
            "confirmed_at": confirmed_at,
            "executor_status": executor_status,
            "applied_records": None if applied_records is None else json.dumps(applied_records),
            "applied_count": len(applied_records) if applied_records is not None else None,
            "executor_timestamp": executor_timestamp,
            "executor_source": "executor" if executor_status is not None else None,
            "created_at": ts,
            "updated_at": ts,
        }
        # post-dry_run states require a recorded confirmation (schema CHECK)
        if state in ("confirmed", "dispatched", "executed", "failed") and row["confirmed_at"] is None:
            row["confirmed_at"] = self.at()
        # executor_result is all-or-nothing; auto-fill for terminal states
        if state in ("executed", "failed") and executor_status is None:
            row["executor_status"] = "applied" if state == "executed" else "failed"
            row["applied_records"] = json.dumps(["node#ws-gpu-11"])
            row["applied_count"] = 1
            row["executor_timestamp"] = self.at(executor_timestamp)
            row["executor_source"] = "executor"
        return row

    def audit_row(
        self,
        *,
        audit_id: str | None = None,
        tool_call_id: str | None = None,
        session_id: str | None = None,
        operator_role: str | None = None,
        timestamp: str | None = None,
        result_summary: dict[str, Any] | None = None,
        actor: str = "copilot",
        proposal_id: str | None = None,
    ) -> dict[str, Any]:
        import json

        return {
            "audit_id": audit_id or self.ids.audit_id(),
            "tool_call_id": tool_call_id,
            "session_id": session_id,
            "operator_role": operator_role,
            "timestamp": self.at(timestamp),
            "result_summary": json.dumps(result_summary or {"ok": True}),
            "actor": actor,
            "proposal_id": proposal_id,
        }

    # -- read-port records (§0.3) -----------------------------------------
    def node_record(
        self,
        *,
        node_id: str = "node#ws-gpu-11",
        hostname: str = "ws-gpu-11",
        gpu_memory_gb: int = 24,
        status: str = "fault",
        cordoned: bool = True,
        error_code: str | None = "ERR_THERMAL_88",
        health: str = "fault",
    ) -> dict[str, Any]:
        return {
            "id": node_id,
            "hostname": hostname,
            "gpu_memory_gb": gpu_memory_gb,
            "status": status,
            "cordoned": cordoned,
            "error_code": error_code,
            "health": health,
        }

    def job_record(
        self,
        *,
        job_id: str = "job#job-8823",
        group_id: str = "group#student-group-07",
        course: str = "cs-4021",
        status: str = "cancelled",
        scheduling_constraint: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": job_id,
            "group_id": group_id,
            "course": course,
            "status": status,
            "scheduling_constraint": scheduling_constraint,
            "created_at": self.at(created_at),
        }

    def user_record(
        self,
        *,
        user_id: str = "user#alex",
        display_name: str = "Alex Rivera",
        role: str = "student",
    ) -> dict[str, Any]:
        return {"id": user_id, "display_name": display_name, "role": role}

    def policy_clause(
        self,
        *,
        clause_id: str = "policy#catalog.4.2",
        model_id: str = "model#llama-3-8b",
        rule: str = "students may not access 40b models",
        reason_class: str = "not-in-allowlist",
        text: str = "Students must not be granted access to models above 8B parameters.",
    ) -> dict[str, Any]:
        return {
            "clause_id": clause_id,
            "model_id": model_id,
            "rule": rule,
            "reason_class": reason_class,
            "text": text,
        }
