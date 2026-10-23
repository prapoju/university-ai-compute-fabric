[
  {
    "location": "ARCHITECTURE.md §3.7 / §5 AD-15",
    "trigger_condition": "executor returns no response after dispatch",
    "guard_snippet": "dispatch() sets state=dispatched then state=failed on 5s timeout; enable re-dispatch from failed only",
    "potential_consequence": "proposal stuck dispatched; operator blocked from re-dispatch"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-3",
    "trigger_condition": "re-dispatch while parent proposal still dispatched",
    "guard_snippet": "reject superseding an in-flight dispatched parent; only failed parents may be superseded",
    "potential_consequence": "two live executor handoffs overlap; double apply across proposals"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-15",
    "trigger_condition": "executor applies fewer items than snapshot lists",
    "guard_snippet": "if applied_count < len(affected_items) then state=failed; render per-item executor result",
    "potential_consequence": "silent partial deletion rendered as success"
  },
  {
    "location": "ARCHITECTURE.md §1.7 / §5 AD-4",
    "trigger_condition": "session reset with a dispatched proposal in flight",
    "guard_snippet": "reset keeps dispatched proposals tracked; surface late executor result when it returns",
    "potential_consequence": "operator cancels flow while executor still applies mutation"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-7",
    "trigger_condition": "follow-up resolves entity from context after state changed",
    "guard_snippet": "re-resolve context-resolved entities against providers before citing them",
    "potential_consequence": "diagnosis cites deleted or altered record"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-7",
    "trigger_condition": "bare name reference with multiple possible entity types",
    "guard_snippet": "route to clarification when the intent does not fix the entity type",
    "potential_consequence": "entity resolved into wrong store; wrong diagnosis"
  },
  {
    "location": "ARCHITECTURE.md §3.1 FR-01",
    "trigger_condition": "one decomposed sub-query Entity-Not-Found, other diagnosed",
    "guard_snippet": "return per-sub-query Answer array; each carries its own chain and canonical response",
    "potential_consequence": "mixed success/failure envelope undefined; render collapses"
  },
  {
    "location": "ARCHITECTURE.md §2.1 / §5 AD-2",
    "trigger_condition": "current time exactly equals window start or end",
    "guard_snippet": "window open when start <= t < end; encode half-open interval in calculator",
    "potential_consequence": "off-by-one next-window at boundary; fixture mismatch"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-2",
    "trigger_condition": "night window crosses midnight; 'today' label applied",
    "guard_snippet": "render explicit date plus timezone for both window edges",
    "potential_consequence": "operator relays wrong day for open window"
  },
  {
    "location": "ARCHITECTURE.md §2.1 FR-06",
    "trigger_condition": "event timestamp equals time-window filter boundary",
    "guard_snippet": "event match on half-open [start, end) interval",
    "potential_consequence": "boundary event excluded or double counted"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-10",
    "trigger_condition": "audit write fails after tool call succeeded",
    "guard_snippet": "if audit insert fails, mark tool call failed and abort the answer",
    "potential_consequence": "FR-11 exactly-one audit entry silently violated"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-10",
    "trigger_condition": "retention rotation deletes oldest audit rows",
    "guard_snippet": "rotation writer identity exempt from delete-denying trigger; log each rotation",
    "potential_consequence": "append-only guarantee has hole or rotation cannot run"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-9",
    "trigger_condition": "node cordoned but error_code empty",
    "guard_snippet": "if error_code null, return no runbook available citing the node record",
    "potential_consequence": "runbook lookup on null code; undefined response"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-9",
    "trigger_condition": "registered runbook template has zero steps",
    "guard_snippet": "reject template at registration when its steps list is empty",
    "potential_consequence": "operator receives empty runbook as actionable guidance"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-10",
    "trigger_condition": "secret-shaped value not matching listed redaction patterns",
    "guard_snippet": "redact any value under credential-named keys regardless of shape",
    "potential_consequence": "unlisted secret shape leaks into audit row"
  },
  {
    "location": "ARCHITECTURE.md §3.2",
    "trigger_condition": "broad browse query returns entire entity store",
    "guard_snippet": "cap browse result count and paginate via page/page_size",
    "potential_consequence": "unbounded state dump on broad browse"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-3",
    "trigger_condition": "second confirm submitted for already-dispatched proposal",
    "guard_snippet": "treat identical proposal plus token confirm as idempotent; else reject 409",
    "potential_consequence": "double-click races dispatch gate; duplicate dispatch attempt"
  },
  {
    "location": "ARCHITECTURE.md §5 AD-8",
    "trigger_condition": "LLM prose contains a forbidden evidence token",
    "guard_snippet": "reject whole prose and retry once; never strip mid-sentence",
    "potential_consequence": "rendered prose broken or silently altered"
  },
  {
    "location": "ARCHITECTURE.md §1.7 / §2.2",
    "trigger_condition": "sessions and answers accumulate without bound",
    "guard_snippet": "apply the same retention cap to sessions and answers as the audit log",
    "potential_consequence": "SQLite growth unbounded; contradicts bounded prototype posture"
  }
]