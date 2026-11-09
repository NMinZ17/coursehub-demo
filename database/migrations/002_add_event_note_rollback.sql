BEGIN;

ALTER TABLE enrollment_events DROP COLUMN note;

DELETE FROM schema_migrations WHERE version = '002';

COMMIT;