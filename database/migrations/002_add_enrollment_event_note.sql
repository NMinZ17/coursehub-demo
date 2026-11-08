-- Existing events keep all their values; note is initially NULL.
-- Run once after migration 001, using psql -v ON_ERROR_STOP=1 -f <file>.
BEGIN;

ALTER TABLE enrollment_events
ADD COLUMN note VARCHAR(200);

INSERT INTO schema_migrations (version, description)
VALUES ('002', 'Add nullable note to enrollment_events');

COMMIT;
