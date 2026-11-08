-- DATA LOSS: every value stored in note is permanently removed.
-- Existing event rows and all their other columns are preserved.
BEGIN;

ALTER TABLE enrollment_events
DROP COLUMN note;

DELETE FROM schema_migrations
WHERE version = '002';

COMMIT;
