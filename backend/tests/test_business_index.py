from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from backend.tests.benchmark_index import (
    CREATE_INDEX_FILE,
    DROP_INDEX_FILE,
    PARAMETERS,
    REPORT_SQL,
    apply_sql_file,
    index_definition,
    report_rows,
    seed_performance_rows,
)


def test_index_preserves_report_and_rollback_removes_only_index(db_engine):
    seed_performance_rows(db_engine, 10_000)
    before = report_rows(db_engine)
    assert before
    assert index_definition(db_engine) is None
    with db_engine.connect() as connection:
        original_count = connection.execute(
            text("SELECT COUNT(*) FROM enrollment_events")
        ).scalar_one()

    apply_sql_file(db_engine, CREATE_INDEX_FILE)
    definition = index_definition(db_engine)
    assert definition is not None
    assert "(class_section_id, event_type, occurred_at)" in definition
    assert report_rows(db_engine) == before

    apply_sql_file(db_engine, DROP_INDEX_FILE)
    assert index_definition(db_engine) is None
    assert report_rows(db_engine) == before
    with db_engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM enrollment_events")
        ).scalar_one() == original_count


def test_report_empty_result(db_engine):
    seed_performance_rows(db_engine, 100)
    parameters = {**PARAMETERS, "class_section_id": "MISSING-SECTION"}
    assert report_rows(db_engine, parameters) == []


def test_report_time_range_includes_start_excludes_end(db_engine):
    with db_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO enrollment_events
                (student_id, class_section_id, event_type, occurred_at)
            VALUES
                ('22000001', 'WEB-01', 'CANCELLED', :start_at),
                ('22000001', 'WEB-01', 'CANCELLED', :end_at),
                ('22000001', 'WEB-01', 'CREATED', :start_at),
                ('22000001', 'WEB-02', 'CANCELLED', :start_at)
        """), PARAMETERS)
    expected = [{"event_date": datetime(2025, 12, 1).date(), "event_count": 1}]
    assert report_rows(db_engine) == expected
    apply_sql_file(db_engine, CREATE_INDEX_FILE)
    assert report_rows(db_engine) == expected


def test_invalid_timestamp_is_rejected_and_connection_recovers(db_engine):
    with pytest.raises(DBAPIError) as error:
        with db_engine.begin() as connection:
            connection.execute(text(REPORT_SQL), {
                **PARAMETERS, "start_at": "not-a-timestamp",
            }).all()
    assert error.value.orig.sqlstate == "22007"
    assert report_rows(db_engine) == []


def test_duplicate_index_is_rejected(db_engine):
    apply_sql_file(db_engine, CREATE_INDEX_FILE)
    with pytest.raises(ProgrammingError) as error:
        apply_sql_file(db_engine, CREATE_INDEX_FILE)
    assert error.value.orig.sqlstate == "42P07"
    assert index_definition(db_engine) is not None
