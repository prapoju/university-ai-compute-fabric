-- 001_module12_copilot_schema.sql
-- Module 12 — AI Operations Copilot — SQLite schema (Phase 2.2)
--
-- Names, types, and invariants mirror planning/detailed-design/contracts.md:
--   §0.1 scalar types (incl. IdKind / IdString), §0.2 entity enums, §0.3 records, §0.4 answer composition,
--   §0.5 safety/proposal types, §2 inbound ops, §3 ports OP-1..OP-15, §4 error catalog, §5 invariants.
--   IdString formats (§0.1, OP-13 idgen_port): sess-|ans-|clm-|tc-|aud-|prop-|evt-[0-9a-f]{16}, gt-[0-9a-f]{32}.
--   Evidence has no independent id (keyed by (answer_id, citation_id)); `evidence` is not an IdKind (X-02).
-- Architecture: planning/ARCHITECTURE.md §2.2 (Module 12-owned entities), AD-1, AD-3, AD-4,
--   AD-6, AD-10, AD-14, AD-15, D42, D46, D50.
--
-- Engine: SQLite (stdlib sqlite3), WAL mode, single writer (ARCHITECTURE Stack Decisions).
-- Requires SQLite >= 3.35 (RETURNING, upsert) and JSON1 (json_valid) — assert sqlite3.sqlite_version at startup (AD-10).
-- Requires SQLite >= 3.9 (partial indexes are older; RETURNING is 3.35).
--
-- NOT declared here (not owned by Module 12): the operational estate (User, Group, ModelCatalogEntry,
-- AccessPolicyClause, Job, Node, Reservation, PolicyWindow, OperationalEvent). Those are read-only and
-- live behind the provider ports (service/ports/out, OP-1..OP-12) — never in this DB (AD-1, AD-13).

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

-- ---------------------------------------------------------------------------
-- sessions  (contracts §2 create_session / get_session / reset_session; ARCH §2.2)
-- ---------------------------------------------------------------------------
CREATE TABLE sessions (
    session_id                TEXT    NOT NULL PRIMARY KEY
                                      CHECK (session_id GLOB 'sess-[0-9a-f]*' AND length(session_id) = 21),
    created_at                TEXT    NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    updated_at                TEXT    NOT NULL CHECK (updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    -- NULL until the first turn; idle age = now - coalesce(last_turn_at, created_at) (E7)
    last_turn_at              TEXT    NULL     CHECK (last_turn_at IS NULL OR last_turn_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    -- E19: the suffix after 'role-' is required and bounded (1..32 chars)
    operator_role             TEXT    NOT NULL CHECK (operator_role GLOB 'role-[a-z0-9_-]*'
                                                      AND length(operator_role) BETWEEN 6 AND 37),
    status                    TEXT    NOT NULL DEFAULT 'active'
                                      CHECK (status IN ('active', 'reset', 'expired')),
    -- A12: expiry is persisted, not merely inferred; the timestamp accompanies the state
    expired_at                TEXT    NULL     CHECK (expired_at IS NULL OR expired_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    -- session.context (contracts §2 Q2) — typed JSON arrays
    context_resolved_entities TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(context_resolved_entities) AND json_type(context_resolved_entities) = 'array'),
    context_prior_intents     TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(context_prior_intents) AND json_type(context_prior_intents) = 'array'),
    context_active_answer_ids TEXT    NOT NULL DEFAULT '[]' CHECK (json_valid(context_active_answer_ids) AND json_type(context_active_answer_ids) = 'array'),
    CHECK (status <> 'expired' OR expired_at IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- answers  (contracts §0.4 Answer; §2 submit_query)
-- ---------------------------------------------------------------------------
CREATE TABLE answers (
    answer_id      TEXT NOT NULL PRIMARY KEY
                          CHECK (answer_id GLOB 'ans-[0-9a-f]*' AND length(answer_id) = 20),
    session_id     TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    query          TEXT NOT NULL CHECK (length(trim(query)) BETWEEN 1 AND 1000),          -- QueryText (§0.1)
    intent         TEXT NOT NULL,                                                         -- IntentCode
    answer_chain   TEXT NOT NULL CHECK (json_valid(answer_chain)),                        -- ordered enum array (§0.4)
    diagnosis_class TEXT NULL CHECK (diagnosis_class IS NULL OR diagnosis_class IN (
                        'access_denial_not_in_allowlist','access_denial_quota','access_denial_window',
                        'schedule_window_restricted','schedule_no_constraint',
                        'event_denied','event_cancelled','event_cordoned',
                        'node_triage_runbook','no_runbook_available')),
    canonical      TEXT NULL CHECK (canonical IS NULL OR canonical IN (
                        'ENTITY_NOT_FOUND','CANNOT_CONFIRM','CLARIFICATION','INTENT_NOT_SUPPORTED',
                        'ACTION_REFUSED')),                                                    -- §0.4 CanonicalCode (D54)
    recommendation TEXT NULL CHECK (recommendation IS NULL OR json_valid(recommendation)), -- object|null
    proposal_ref   TEXT NULL,                                                              -- string|null
    prose          TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    updated_at     TEXT NOT NULL CHECK (updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z')
);
CREATE INDEX ix_answers_session ON answers(session_id);

-- ---------------------------------------------------------------------------
-- evidence  (contracts §0.4 EvidenceSet; AD-14)
-- Invariant: UNIQUE(answer_id, citation_id) (via PK) + position NOT NULL, monotonic (unique per answer).
-- ---------------------------------------------------------------------------
CREATE TABLE evidence (
    answer_id   TEXT    NOT NULL REFERENCES answers(answer_id) ON DELETE CASCADE,
    citation_id TEXT    NOT NULL,                                              -- EntityKey | clock#id  (§0.1)
    source_type TEXT    NOT NULL CHECK (source_type IN (
                        'user','group','model','policy','node','job',
                        'reservation','window','event','clock')),
    snippet     TEXT    NOT NULL CHECK (
                        (source_type = 'policy' AND length(snippet) BETWEEN 1 AND 2000) OR
                        (source_type <> 'policy' AND length(snippet) BETWEEN 1 AND 500)),  -- §0.1 Snippet
    position    INTEGER NOT NULL CHECK (position >= 0),
    created_at  TEXT    NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    PRIMARY KEY (answer_id, citation_id),        -- AD-14: (answer_id, citation_id) UNIQUE
    UNIQUE (answer_id, position)                 -- AD-14: position is unique & monotonic per answer
    -- E21: positions must be the contiguous sequence 0..n-1; UNIQUE(answer_id, position) is the
    -- physical backstop, and the evidence composer asserts start==0 with no gaps at write time.
);

-- ---------------------------------------------------------------------------
-- claims  (contracts §0.4 Claim; AD-8)
-- ---------------------------------------------------------------------------
CREATE TABLE claims (
    claim_id   TEXT NOT NULL PRIMARY KEY
                      CHECK (claim_id GLOB 'clm-[0-9a-f]*' AND length(claim_id) = 20),
    answer_id  TEXT NOT NULL REFERENCES answers(answer_id) ON DELETE CASCADE,
    text       TEXT NOT NULL CHECK (length(trim(text)) >= 1),   -- E20: non-empty claim text
    created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z')
);
CREATE INDEX ix_claims_answer ON claims(answer_id);

-- ---------------------------------------------------------------------------
-- claim_citations  (join; contracts §0.4 Claim.claim_citations; AD-8, AD-14)
-- FK column is a join, never a single FK column (AD-14).
-- ">= 1 citation per claim": enforced on the destructive side by trigger
--   trg_claim_citations_guard_delete; the insert side cannot be a deferred CHECK in
--   SQLite (see phase-2.3-cross-check.md, finding X-01).
-- ---------------------------------------------------------------------------
CREATE TABLE claim_citations (
    claim_id    TEXT NOT NULL,
    answer_id   TEXT NOT NULL,
    citation_id TEXT NOT NULL,
    PRIMARY KEY (claim_id, citation_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
    FOREIGN KEY (answer_id, citation_id) REFERENCES evidence(answer_id, citation_id) ON DELETE CASCADE
);
CREATE INDEX ix_claim_citations_evidence ON claim_citations(answer_id, citation_id);

-- ---------------------------------------------------------------------------
-- tool_calls  (contracts §4 toolcall.*; ARCH §2.2 ToolCall)
-- ---------------------------------------------------------------------------
CREATE TABLE tool_calls (
    tool_call_id   TEXT NOT NULL PRIMARY KEY
                          CHECK (tool_call_id GLOB 'tc-[0-9a-f]*' AND length(tool_call_id) = 19),
    session_id     TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    tool_name      TEXT NOT NULL,                                            -- e.g. toolcall.answer_query
    params_summary TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(params_summary)),
    timestamp      TEXT NOT NULL CHECK (timestamp GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    status         TEXT NOT NULL CHECK (status IN ('ok', 'failure')),
    created_at     TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z')
);
CREATE INDEX ix_tool_calls_session ON tool_calls(session_id);

-- ---------------------------------------------------------------------------
-- proposals  (contracts §0.5 Proposal; AD-3, AD-4, AD-6, AD-15)
-- ---------------------------------------------------------------------------
CREATE TABLE proposals (
    proposal_id            TEXT NOT NULL PRIMARY KEY
                               CHECK (proposal_id GLOB 'prop-[0-9a-f]*' AND length(proposal_id) = 21),
    session_id             TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    state                  TEXT NOT NULL CHECK (state IN (
                               'refused','dry_run','confirmed','dispatched','executed','failed','superseded')),
    action                 TEXT NOT NULL CHECK (action IN (
                               'delete_jobs','cancel_jobs','cordon_node','drain_node')),   -- ActionVerb (§0.1)
    supersedes_proposal_id TEXT NULL REFERENCES proposals(proposal_id) ON DELETE SET NULL,
    -- DryRunSnapshot (§0.5)
    -- E39: selector.method is allowlisted to the vetted provider queries before it is persisted
    selector               TEXT NOT NULL CHECK (json_valid(selector)
                                                  AND json_type(selector) = 'object'
                                                  AND json_extract(selector, '$.method') IN
                                                      ('jobs_port.select', 'nodes_port.select')),
    -- E40: affected_items must be a JSON array (item shape asserted by the dry-run composer)
    affected_items         TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(affected_items)
                                                  AND json_type(affected_items) = 'array'),
    snapshot_timestamp     TEXT NOT NULL CHECK (snapshot_timestamp GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    gate_token             TEXT NOT NULL UNIQUE CHECK (gate_token GLOB 'gt-[0-9a-f]*' AND length(gate_token) = 35),  -- E22: a token confirms at most one proposal
    confirmed_at           TEXT NULL CHECK (confirmed_at IS NULL OR confirmed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    -- executor_result (§0.5)
    executor_status        TEXT NULL CHECK (executor_status IS NULL OR executor_status IN ('applied','partial','failed')),
    applied_records        TEXT NULL CHECK (applied_records IS NULL OR json_valid(applied_records)), -- EntityKey[]
    applied_count          INTEGER NULL CHECK (applied_count IS NULL OR applied_count >= 0),
    executor_timestamp     TEXT NULL CHECK (executor_timestamp IS NULL OR executor_timestamp GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    executor_source        TEXT NULL CHECK (executor_source IS NULL OR executor_source = 'executor'),
    created_at             TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    updated_at             TEXT NOT NULL CHECK (updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    -- lifecycle shape guards (AD-3, AD-4): states after dry_run require a recorded confirmation
    CHECK (state NOT IN ('confirmed','dispatched','executed','failed') OR confirmed_at IS NOT NULL),
    -- executor_result is all-or-nothing
    CHECK ((executor_status IS NULL AND applied_records IS NULL AND applied_count IS NULL
            AND executor_timestamp IS NULL AND executor_source IS NULL)
        OR (executor_status IS NOT NULL AND applied_records IS NOT NULL AND applied_count IS NOT NULL
            AND executor_timestamp IS NOT NULL AND executor_source = 'executor')),
    -- D33: partial apply => failed
    CHECK (executor_status <> 'partial' OR state = 'failed')
);
CREATE INDEX ix_proposals_session ON proposals(session_id);
CREATE INDEX ix_proposals_supersedes ON proposals(supersedes_proposal_id);

-- ---------------------------------------------------------------------------
-- audit_records  (contracts §2 execute/audit; ARCH §2.2 AuditRecord; AD-10, AD-15, D42, D50)
-- Append-only. Exactly one row per copilot tool call; exactly one executor-applied row per proposal.
-- ---------------------------------------------------------------------------
CREATE TABLE audit_records (
    audit_id       TEXT NOT NULL PRIMARY KEY
                          CHECK (audit_id GLOB 'aud-[0-9a-f]*' AND length(audit_id) = 20),
    -- A29 (deferred): RESTRICT here vs tool_calls CASCADE from sessions is unexercised (no delete route exists);
    -- the prototype re-creates the DB. Revisit if a session-delete route is added.
    tool_call_id   TEXT NULL REFERENCES tool_calls(tool_call_id) ON DELETE RESTRICT,
    session_id     TEXT NULL REFERENCES sessions(session_id) ON DELETE SET NULL,
    operator_role  TEXT NULL,
    timestamp      TEXT NOT NULL CHECK (timestamp GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    result_summary TEXT NOT NULL CHECK (json_valid(result_summary)),
    actor          TEXT NOT NULL CHECK (actor IN ('copilot','executor')),
    proposal_id    TEXT NULL REFERENCES proposals(proposal_id) ON DELETE SET NULL,
    -- AD-10: executor-applied rows carry actor=executor, proposal_id, and null tool_call_id
    CHECK (actor <> 'executor' OR (tool_call_id IS NULL AND proposal_id IS NOT NULL))
);

-- AD-10 / I14: exactly one audit row per copilot tool call
CREATE UNIQUE INDEX ux_audit_tool_call
    ON audit_records(tool_call_id) WHERE tool_call_id IS NOT NULL;
-- AD-15 / I10: exactly one executor-applied record per proposal (no double-apply)
CREATE UNIQUE INDEX ux_audit_executor_apply
    ON audit_records(proposal_id) WHERE actor = 'executor';
 -- E47: audit_id is the deterministic secondary sort key so page order is stable across reads
CREATE INDEX ix_audit_session_ts ON audit_records(session_id, timestamp, audit_id);

-- D42 rotation-writer exemption gate. SQLite has no session identity, so the rotation writer
-- opens the gate inside its transaction; the delete trigger permits deletes only while open.
-- E26: exactly one rotation writer may run; it holds the gate open inside a single BEGIN IMMEDIATE
-- transaction (see C9) so a concurrent writer cannot bypass or block the delete trigger.
CREATE TABLE audit_rotation_gate (
    gate_id   INTEGER NOT NULL PRIMARY KEY CHECK (gate_id = 1),
    gate_open INTEGER NOT NULL DEFAULT 0 CHECK (gate_open IN (0, 1))
);
INSERT INTO audit_rotation_gate (gate_id, gate_open) VALUES (1, 0);

-- ---------------------------------------------------------------------------
-- audit_events  (Phase 2.2: append-only telemetry event log; see events.md / events.schema.json)
-- Distinct from audit_records (tool-call audit). One envelope per emitted/ingested event.
-- ---------------------------------------------------------------------------
CREATE TABLE audit_events (
    event_id       TEXT NOT NULL PRIMARY KEY,
    event_type     TEXT NOT NULL CHECK (event_type IN (
                       'operational_event_ingested',   -- ingested (OperationalEvent)
                       'tool_call',                    -- emitted
                       'audit',                        -- emitted
                       'proposal_lifecycle',           -- emitted
                       'answer_produced')),            -- emitted
    schema_version TEXT NOT NULL,
    occurred_at    TEXT NOT NULL CHECK (occurred_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    session_id     TEXT NULL REFERENCES sessions(session_id) ON DELETE SET NULL,
    payload        TEXT NOT NULL CHECK (json_valid(payload)),
    created_at     TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*Z'),
    -- A28: session-scoped event types must carry a session_id (schema-level required:[sessionId])
    CHECK (event_type NOT IN ('tool_call', 'answer_produced') OR session_id IS NOT NULL)
);
CREATE INDEX ix_audit_events_type_ts ON audit_events(event_type, occurred_at);

-- ---------------------------------------------------------------------------
-- Triggers — physically enforced invariants
-- ---------------------------------------------------------------------------

-- AD-10: audit_records is append-only: no UPDATE, ever.
CREATE TRIGGER trg_audit_records_no_update
BEFORE UPDATE ON audit_records
BEGIN
    SELECT RAISE(ABORT, 'audit_records is append-only (AD-10): UPDATE denied');
END;

-- AD-10 + D42: DELETE denied unless the rotation-writer gate is open (retention rotation only).
CREATE TRIGGER trg_audit_records_no_delete
BEFORE DELETE ON audit_records
WHEN (SELECT gate_open FROM audit_rotation_gate WHERE gate_id = 1) <> 1
BEGIN
    SELECT RAISE(ABORT, 'audit_records is append-only (AD-10): DELETE denied; D42 rotation gate closed');
END;

-- audit_events is append-only: no UPDATE / DELETE.
CREATE TRIGGER trg_audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: UPDATE denied');
END;
CREATE TRIGGER trg_audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: DELETE denied');
END;

-- AD-8 / I3: a claim_citations row cannot be the last citation of a claim (>= 1 per claim, delete side).
CREATE TRIGGER trg_claim_citations_guard_delete
BEFORE DELETE ON claim_citations
WHEN (SELECT COUNT(*) FROM claim_citations WHERE claim_id = OLD.claim_id) <= 1
BEGIN
    SELECT RAISE(ABORT, 'claim_citations: a claim must retain >= 1 citation (AD-8)');
END;

-- E38: context_* arrays may contain only string elements (EntityKey / IntentCode / id strings).
CREATE TRIGGER trg_sessions_context_types_insert
BEFORE INSERT ON sessions
WHEN EXISTS (SELECT 1 FROM json_each(NEW.context_resolved_entities) WHERE type <> 'text')
  OR EXISTS (SELECT 1 FROM json_each(NEW.context_prior_intents)     WHERE type <> 'text')
  OR EXISTS (SELECT 1 FROM json_each(NEW.context_active_answer_ids) WHERE type <> 'text')
BEGIN
    SELECT RAISE(ABORT, 'sessions.context_* elements must be strings (E38)');
END;

CREATE TRIGGER trg_sessions_context_types_update
BEFORE UPDATE OF context_resolved_entities, context_prior_intents, context_active_answer_ids ON sessions
WHEN EXISTS (SELECT 1 FROM json_each(NEW.context_resolved_entities) WHERE type <> 'text')
  OR EXISTS (SELECT 1 FROM json_each(NEW.context_prior_intents)     WHERE type <> 'text')
  OR EXISTS (SELECT 1 FROM json_each(NEW.context_active_answer_ids) WHERE type <> 'text')
BEGIN
    SELECT RAISE(ABORT, 'sessions.context_* elements must be strings (E38)');
END;

-- AD-4: proposal state transitions are constrained to the ordered state machine.
-- (Conditional-UPDATE statements in the "contended writes" section below are the runtime guards;
--  this trigger blocks illegal jumps even from ad-hoc SQL.)
CREATE TRIGGER trg_proposals_state_machine
BEFORE UPDATE OF state ON proposals
WHEN NOT (
       (OLD.state = 'refused'    AND NEW.state IN ('refused','dry_run')) OR
       (OLD.state = 'dry_run'    AND NEW.state IN ('dry_run','confirmed')) OR
       (OLD.state = 'confirmed'  AND NEW.state IN ('confirmed','dispatched')) OR
       (OLD.state = 'dispatched' AND NEW.state IN ('dispatched','executed','failed')) OR
       (OLD.state IN ('executed','failed','superseded') AND NEW.state = OLD.state)
   )
BEGIN
    SELECT RAISE(ABORT, 'proposals: illegal state transition (AD-4)');
END;

-- ---------------------------------------------------------------------------
-- Contended writes — the exact atomic statement that serializes each
-- Rule: no "SELECT then UPDATE". Every contended mutation is a single conditional
-- statement (or a short BEGIN IMMEDIATE ... COMMIT block of them) whose WHERE re-checks
-- the state predicate, using RETURNING * to read the post-state.
-- Execute the mutating statements inside:  BEGIN IMMEDIATE; ... COMMIT;
-- ---------------------------------------------------------------------------

-- C1. create_session — PK uniqueness serializes id collision; single INSERT.
--     INSERT INTO sessions (session_id, created_at, updated_at, last_turn_at, operator_role, status)
--     VALUES (:sid, :now, :now, NULL, :role, 'active');
--
-- C2. submit_query — append one entry PER RETURNED ANSWER under the per-session single writer;
--     conditional UPDATE on the live-session predicate (rejects expired/reset without a preceding
--     SELECT). A compound query (D37, len(answers) >= 2) contributes >= 2 entries per context array,
--     so the arrays are pre-merged and written atomically in the same BEGIN IMMEDIATE block (A19):
--     UPDATE sessions
--        SET context_resolved_entities = :resolved,
--            context_prior_intents     = :prior_intents,      -- len == len(answers)
--            context_active_answer_ids = :active_answer_ids,  -- len == len(answers)
--            last_turn_at = :now, updated_at = :now
--      WHERE session_id = :sid AND status = 'active'
--      RETURNING *;                          -- 0 rows => SESSION_NOT_FOUND / SESSION_EXPIRED
--     -- A12 expiry write-back is idempotent and converges before the queued turn:
--     UPDATE sessions SET status = 'expired', expired_at = :now, updated_at = :now
--      WHERE session_id = :sid AND status = 'active'
--        AND coalesce(last_turn_at, created_at) < :idle_cutoff;   -- E7: NULL last_turn_at uses created_at
--
-- C3. reset_session — single conditional UPDATE; idempotent by predicate, not by prior read:
--     UPDATE sessions
--        SET status = 'reset',
--            context_resolved_entities = '[]', context_prior_intents = '[]',
--            context_active_answer_ids = '[]', updated_at = :now
--      WHERE session_id = :sid
--      RETURNING *;
--
-- C4. assemble_evidence — idempotent insert; PK (answer_id, citation_id) dedupes:
--     INSERT INTO evidence (answer_id, citation_id, source_type, snippet, position, created_at)
--     VALUES (:answer_id, :citation_id, :source_type, :snippet, :position, :now)
--     ON CONFLICT(answer_id, citation_id) DO NOTHING;
--
-- C5. confirm_and_dispatch — the canonical example. Dispatch is only legal from `confirmed`;
--     the confirmation transition is a single conditional UPDATE keyed on the dry-run state + gate token:
--     UPDATE proposals
--        SET state = 'confirmed', confirmed_at = :now, updated_at = :now
--      WHERE proposal_id = :pid AND state = 'dry_run' AND gate_token = :gt
--      RETURNING *;                          -- 0 rows => PROPOSAL_NOT_FOUND / PROPOSAL_STATE_INVALID / GATE_TOKEN_INVALID
--     -- then the guarded dispatch transition (exactly one per confirmed proposal):
--     UPDATE proposals
--        SET state = 'dispatched', updated_at = :now
--      WHERE proposal_id = :pid AND state = 'confirmed'
--      RETURNING *;                          -- 0 rows => CONFIRMATION_CONFLICT (already dispatched)
--
-- C6. executor result recording — single conditional UPDATE from dispatched:
--     UPDATE proposals
--        SET state = :final_state,             -- executed | failed
--            executor_status = :status, applied_records = :applied,
--            applied_count = :n, executor_timestamp = :ts, executor_source = 'executor',
--            updated_at = :now
--      WHERE proposal_id = :pid AND state = 'dispatched'
--      RETURNING *;                          -- 0 rows => already resolved (idempotent re-read)
--
-- C7. re-dispatch supersede — only a `failed` parent may be superseded:
--     UPDATE proposals
--        SET state = 'superseded', updated_at = :now
--      WHERE proposal_id = :parent AND state = 'failed'
--      RETURNING *;                          -- 0 rows => PROPOSAL_STATE_INVALID
--
-- C8. audit write — the unique partial indexes ux_audit_tool_call / ux_audit_executor_apply are
--     the serialization point; a duplicate raises SQLITE_CONSTRAINT (AUDIT_WRITE_FAILED / double-apply):
--     INSERT INTO audit_records
--       (audit_id, tool_call_id, session_id, operator_role, timestamp, result_summary, actor, proposal_id)
--     VALUES (:audit_id, :tool_call_id, :sid, :role, :now, :summary, :actor, :pid);
--
-- C9. retention rotation (D42/D50) — open gate, delete oldest, close gate, all in one transaction:
--     BEGIN IMMEDIATE;
--       UPDATE audit_rotation_gate SET gate_open = 1 WHERE gate_id = 1;
--       DELETE FROM audit_records WHERE audit_id IN (
--         SELECT audit_id FROM audit_records ORDER BY timestamp ASC, audit_id ASC LIMIT :excess);
--       UPDATE audit_rotation_gate SET gate_open = 0 WHERE gate_id = 1;
--     COMMIT;
