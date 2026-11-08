-- 002: let a failed proposal be superseded by its re-dispatch (contracts C7, story 2.4, AD-4).
-- Migration 001 states the contended write C7 (`UPDATE ... SET state = 'superseded' WHERE state =
-- 'failed'`) but its trigger only lets `failed` stay `failed`, so `superseded` could never be
-- reached. 001 is not edited (its checksum is recorded); the trigger is replaced here, with one
-- more legal step and nothing else changed.
DROP TRIGGER trg_proposals_state_machine;

CREATE TRIGGER trg_proposals_state_machine
BEFORE UPDATE OF state ON proposals
WHEN NOT (
       (OLD.state = 'refused'    AND NEW.state IN ('refused','dry_run')) OR
       (OLD.state = 'dry_run'    AND NEW.state IN ('dry_run','confirmed')) OR
       (OLD.state = 'confirmed'  AND NEW.state IN ('confirmed','dispatched')) OR
       (OLD.state = 'dispatched' AND NEW.state IN ('dispatched','executed','failed')) OR
       (OLD.state = 'failed'     AND NEW.state IN ('failed','superseded')) OR
       (OLD.state IN ('executed','superseded') AND NEW.state = OLD.state)
   )
BEGIN
    SELECT RAISE(ABORT, 'proposals: illegal state transition (AD-4)');
END;
