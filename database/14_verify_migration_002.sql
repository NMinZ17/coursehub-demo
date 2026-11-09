
CREATE TEMP TABLE hw04_events_before AS
SELECT id, student_id, class_section_id, event_type, source, dataset, occurred_at
FROM enrollment_events;

SELECT COUNT(*) AS rows_before FROM hw04_events_before;


WITH current_original AS (
    SELECT id, student_id, class_section_id,
           event_type, source, dataset, occurred_at
    FROM enrollment_events
), differences AS (
    (SELECT * FROM hw04_events_before EXCEPT ALL SELECT * FROM current_original)
    UNION ALL
    (SELECT * FROM current_original EXCEPT ALL SELECT * FROM hw04_events_before)
)
SELECT COUNT(*) AS changed_original_rows FROM differences;

SELECT COUNT(*) AS rows_after,
       COUNT(note) AS non_null_notes
FROM enrollment_events;


SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = 'enrollment_events' AND column_name = 'note';

SELECT version, description FROM schema_migrations ORDER BY version;

SELECT COUNT(*) AS note_columns
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = 'enrollment_events' AND column_name = 'note';