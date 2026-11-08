"""Create disposable schemas; never insert/update/delete source application data."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
if os.getenv("COURSEHUB_ENV_FILE"):
    load_dotenv(os.environ["COURSEHUB_ENV_FILE"])

from backend.app.database import engine as source_engine


def source_state() -> dict:
    """Fingerprint rows, columns, indexes and sequence values in the source schema."""
    with source_engine.connect() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        quote = connection.dialect.identifier_preparer.quote
        tables = connection.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = :schema ORDER BY tablename
        """), {"schema": schema}).scalars().all()
        rows = {}
        for table in tables:
            qualified = f"{quote(schema)}.{quote(table)}"
            count, digest = connection.execute(text(f"""
                SELECT COUNT(*), md5(COALESCE(
                    string_agg(row_to_json(t)::text, E'\\n'
                               ORDER BY row_to_json(t)::text), ''
                )) FROM {qualified} AS t
            """)).one()
            rows[table] = {"count": count, "md5": digest}
        columns = connection.execute(text("""
            SELECT table_name, column_name, data_type,
                   character_maximum_length, is_nullable, column_default,
                   is_identity, identity_generation
            FROM information_schema.columns
            WHERE table_schema = :schema ORDER BY table_name, ordinal_position
        """), {"schema": schema}).all()
        indexes = connection.execute(text("""
            SELECT tablename, indexname, indexdef FROM pg_indexes
            WHERE schemaname = :schema ORDER BY tablename, indexname
        """), {"schema": schema}).all()
        sequences = connection.execute(text("""
            SELECT sequencename, start_value, min_value, max_value,
                   increment_by, cycle, cache_size, last_value
            FROM pg_sequences WHERE schemaname = :schema
            ORDER BY sequencename
        """), {"schema": schema}).all()
        return {"schema": schema, "tables": rows,
                "columns": [list(row) for row in columns],
                "indexes": [list(row) for row in indexes],
                "sequences": [list(row) for row in sequences]}


@contextmanager
def isolated_database():
    """Yield a real PostgreSQL Engine with only a random test schema in search_path.

    Bootstrap the project's schema, seed, migration 001 and first index. Even an
    unexpected commit affects only this schema, including its identity sequence.
    DROP SCHEMA runs in finally; the original schema must compare equal afterward.
    """
    baseline = source_state()
    schema = "coursehub_test_" + uuid4().hex
    assert re.fullmatch(r"coursehub_test_[0-9a-f]{32}", schema)
    test_engine = create_engine(
        source_engine.url, pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    created = False
    try:
        with source_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        created = True
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            assert connection.execute(text("SELECT current_schema()")).scalar_one() == schema
            for filename in (
                "database/01_schema.sql",
                "database/02_seed.sql",
                "database/migrations/001_add_enrollment_events.sql",
                "database/04_views.sql",
            ):
                connection.exec_driver_sql((ROOT / filename).read_text(encoding="utf-8"))
            connection.exec_driver_sql("""
                CREATE INDEX idx_enrollment_events_dataset_student_time
                ON enrollment_events (dataset, student_id, occurred_at DESC)
            """)
        yield test_engine
    finally:
        test_engine.dispose()
        if created:
            # schema is generated locally and validated above, never a user value.
            with source_engine.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            with source_engine.connect() as connection:
                assert connection.execute(text(
                    "SELECT COUNT(*) FROM pg_namespace WHERE nspname = :schema"
                ), {"schema": schema}).scalar_one() == 0
        assert source_state() == baseline, "Source schema changed during tests"
