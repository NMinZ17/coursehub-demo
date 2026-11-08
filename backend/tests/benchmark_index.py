"""Reproducible Bài 3 benchmark, exclusively inside a disposable test schema."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from statistics import median

from sqlalchemy import Engine, text

from backend.tests.support import isolated_database


ROOT = Path(__file__).resolve().parents[2]
INDEX_NAME = "idx_enrollment_events_section_type_time"
CREATE_INDEX_FILE = ROOT / "database/13_enrollment_events_business_index.sql"
DROP_INDEX_FILE = ROOT / "database/13_enrollment_events_business_index_rollback.sql"

REPORT_SQL = """
    SELECT occurred_at::date AS event_date, COUNT(*) AS event_count
    FROM enrollment_events
    WHERE class_section_id = :class_section_id
      AND event_type = :event_type
      AND occurred_at >= :start_at
      AND occurred_at < :end_at
    GROUP BY occurred_at::date
    ORDER BY event_date
"""

PARAMETERS = {
    "class_section_id": "WEB-01",
    "event_type": "CANCELLED",
    "start_at": datetime(2025, 12, 1),
    "end_at": datetime(2026, 1, 1),
}


def apply_sql_file(engine: Engine, path: Path) -> None:
    """The supplied deployment scripts own their BEGIN/COMMIT boundaries."""
    with engine.connect() as connection:
        connection.exec_driver_sql(path.read_text(encoding="utf-8"))
        connection.commit()


def index_definition(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text("""
                SELECT indexdef FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND tablename = 'enrollment_events'
                  AND indexname = :index_name
            """),
            {"index_name": INDEX_NAME},
        ).scalar_one_or_none()


def seed_performance_rows(engine: Engine, row_count: int = 100_000) -> None:
    if row_count < 1:
        raise ValueError("row_count must be positive")
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO enrollment_events
                    (student_id, class_section_id, event_type,
                     source, dataset, occurred_at)
                SELECT
                    (ARRAY['22000001', '22000002', '22000003', '22000004'])
                        [1 + (g % 4)::INTEGER],
                    (ARRAY['WEB-01', 'WEB-02', 'DM-01', 'PY-01'])
                        [1 + (g % 4)::INTEGER],
                    CASE WHEN g % 5 = 0 THEN 'CANCELLED' ELSE 'CREATED' END,
                    'benchmark-bai3',
                    'performance',
                    TIMESTAMP '2025-01-01 00:00:00'
                        + (g % 365) * INTERVAL '1 day'
                        + (g % 86400) * INTERVAL '1 second'
                FROM generate_series(1, :row_count) AS g
            """),
            {"row_count": row_count},
        )
        # Preserve the first index from week 4 while testing the second index.
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_enrollment_events_dataset_student_time
            ON enrollment_events (dataset, student_id, occurred_at DESC)
        """))
        connection.execute(text("ANALYZE enrollment_events"))


def report_rows(engine: Engine, parameters: dict | None = None) -> list[dict]:
    with engine.connect() as connection:
        return [
            dict(row) for row in connection.execute(
                text(REPORT_SQL),
                PARAMETERS if parameters is None else parameters,
            ).mappings()
        ]


def measure(engine: Engine, repetitions: int = 5) -> dict:
    explain_sql = text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + REPORT_SQL)
    with engine.connect() as connection:
        connection.execute(explain_sql, PARAMETERS).scalar_one()  # warm-up
        plans = [
            connection.execute(explain_sql, PARAMETERS).scalar_one()[0]
            for _ in range(repetitions)
        ]
    return {
        "warmup_runs": 1,
        "measured_runs": repetitions,
        "median_execution_ms": median(plan["Execution Time"] for plan in plans),
        "median_planning_ms": median(plan["Planning Time"] for plan in plans),
        "median_shared_hit_blocks": median(
            plan["Plan"].get("Shared Hit Blocks", 0) for plan in plans
        ),
        "median_shared_read_blocks": median(
            plan["Plan"].get("Shared Read Blocks", 0) for plan in plans
        ),
        "plans": plans,
    }


def run_benchmark(row_count: int = 100_000) -> dict:
    with isolated_database() as engine:
        if index_definition(engine) is not None:
            raise RuntimeError("The second index must be absent before measurement")
        seed_performance_rows(engine, row_count)
        with engine.connect() as connection:
            server_version = connection.execute(text("SELECT version()")).scalar_one()
            schema_name = connection.execute(text("SELECT current_schema()")).scalar_one()
            total_rows = connection.execute(
                text("SELECT COUNT(*) FROM enrollment_events")
            ).scalar_one()
            first_index_present = connection.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND indexname = 'idx_enrollment_events_dataset_student_time'
                )
            """)).scalar_one()

        before_rows = report_rows(engine)
        before = measure(engine)

        apply_sql_file(engine, CREATE_INDEX_FILE)
        with engine.begin() as connection:
            connection.execute(text("ANALYZE enrollment_events"))

        after_rows = report_rows(engine)
        after = measure(engine)
        if before_rows != after_rows:
            raise AssertionError("Creating the index changed the query results")

        result = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "server_version": server_version,
            "test_schema": schema_name,
            "generated_rows": row_count,
            "total_rows": total_rows,
            "first_index_present": first_index_present,
            "query": REPORT_SQL.strip(),
            "parameters": PARAMETERS,
            "index_definition": index_definition(engine),
            "results_equal": True,
            "result_rows": after_rows,
            "before": before,
            "after": after,
        }
    # Only report cleanup after the context manager has removed the schema
    # and verified that the original database snapshot remains unchanged.
    result["cleanup_confirmed"] = True
    return result


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/evidence/index_benchmark.json"
    )
    parser.add_argument("--rows", type=int, default=100_000)
    args = parser.parse_args()
    result = run_benchmark(args.rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "before_ms": result["before"]["median_execution_ms"],
        "after_ms": result["after"]["median_execution_ms"],
        "results_equal": result["results_equal"],
        "cleanup_confirmed": result["cleanup_confirmed"],
        "evidence": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
