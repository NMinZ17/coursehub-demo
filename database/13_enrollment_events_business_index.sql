BEGIN;

-- Query: one section, one event type, then a half-open time range.
CREATE INDEX idx_enrollment_events_section_type_time
ON enrollment_events (class_section_id, event_type, occurred_at);

COMMIT;
