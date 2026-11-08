# CourseHub - Buoi 4
- Migration 001: enrollment_events.
- Demo class: RACE-01, capacity = 1.
- POST /enrollments: lock class_sections bang FOR UPDATE.
- Concurrency test: 1 request 201, 1 request 409.
- Performance data: 100000 rows, dataset=performance.
- Index: idx_enrollment_events_dataset_student_time.

# Trước khi tạo index
    "Limit  (cost=0.42..68.08 rows=50 width=39) (actual time=0.037..0.066 rows=50.00 loops=1)"
    "  Buffers: shared hit=53"
    "  ->  Index Scan using idx_enrollment_events_dataset_student_time on enrollment_events  (cost=0.42..1081.71 rows=799 width=39) (actual time=0.036..0.063 rows=50.00 loops=1)"
    "        Index Cond: (((dataset)::text = 'performance'::text) AND ((student_id)::text = '22000001'::text) AND (occurred_at >= '2025-12-20 00:00:00'::timestamp without time zone))"
    "        Index Searches: 1"
    "        Buffers: shared hit=53"
    "Planning Time: 0.079 ms"
    "Execution Time: 0.077 ms"

# Sau khi tạo index
    "Limit  (cost=0.42..68.08 rows=50 width=39) (actual time=0.043..0.084 rows=50.00 loops=1)"
    "  Buffers: shared hit=53"
    "  ->  Index Scan using idx_enrollment_events_dataset_student_time on enrollment_events  (cost=0.42..1081.71 rows=799 width=39) (actual time=0.042..0.080 rows=50.00 loops=1)"
    "        Index Cond: (((dataset)::text = 'performance'::text) AND ((student_id)::text = '22000001'::text) AND (occurred_at >= '2025-12-20 00:00:00'::timestamp without time zone))"
    "        Index Searches: 1"
    "        Buffers: shared hit=53"
    "Planning Time: 0.107 ms"
    "Execution Time: 0.102 ms"

Khong commit backend/.env.