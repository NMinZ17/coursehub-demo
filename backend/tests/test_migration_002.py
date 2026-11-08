"""Exercise 4: execute the real SQL files against a populated test schema."""
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"
UP = MIGRATIONS / "002_add_enrollment_event_note.sql"
DOWN = MIGRATIONS / "002_add_enrollment_event_note_rollback.sql"
OLD_COLUMNS = (
    "id, student_id, class_section_id, event_type, source, dataset, occurred_at"
)


def run_migration(db_engine, path):
    """Respect BEGIN/COMMIT in the SQL file and recover failed transactions."""
    with db_engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        try:
            connection.exec_driver_sql(path.read_text(encoding="utf-8"))
        except DBAPIError:
            # An explicit BEGIN in the script remains aborted after SQL errors.
            # Send ROLLBACK explicitly even though the DBAPI uses autocommit.
            connection.exec_driver_sql("ROLLBACK")
            raise


def old_rows(db_engine):
    with db_engine.connect() as connection:
        return connection.execute(
            text(f"SELECT {OLD_COLUMNS} FROM enrollment_events ORDER BY id")
        ).all()


def note_column(db_engine):
    with db_engine.connect() as connection:
        row = connection.execute(text("""
            SELECT data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'enrollment_events'
              AND column_name = 'note'
        """)).first()
    return tuple(row) if row is not None else None


def migration_rows(db_engine):
    with db_engine.connect() as connection:
        return connection.execute(text("""
            SELECT version, description, applied_at
            FROM schema_migrations ORDER BY version
        """)).all()


@pytest.fixture
def populated_events(db_engine):
    # These rows exist and are committed BEFORE the migration is executed.
    with db_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO enrollment_events
                (student_id, class_section_id, event_type, source, dataset,
                 occurred_at)
            VALUES
                ('22000001', 'WEB-01', 'CREATED', 'test-migration002', 'demo',
                 TIMESTAMP '2026-10-01 08:00:00'),
                ('22000001', 'WEB-01', 'CANCELLED', 'test-migration002', 'demo',
                 TIMESTAMP '2026-10-02 09:30:00'),
                ('22000004', 'WEB-02', 'CREATED', 'test-migration002', 'demo',
                 TIMESTAMP '2026-10-03 10:00:00')
        """))
    rows = old_rows(db_engine)
    assert len(rows) >= 3
    return rows


def test_up_preserves_every_old_value_and_registers_version(
    db_engine, populated_events
):
    before_versions = migration_rows(db_engine)
    assert note_column(db_engine) is None

    run_migration(db_engine, UP)

    assert old_rows(db_engine) == populated_events
    assert note_column(db_engine) == ("character varying", 200, "YES")
    versions = migration_rows(db_engine)
    assert [row for row in versions if row.version != "002"] == before_versions
    assert len([row for row in versions if row.version == "002"]) == 1
    with db_engine.connect() as connection:
        assert connection.execute(text("""
            SELECT COUNT(*) FROM enrollment_events WHERE note IS NOT NULL
        """)).scalar_one() == 0


@pytest.mark.parametrize("note", ["a" * 200, "ộ" * 200, None])
def test_note_accepts_200_characters_and_null(db_engine, populated_events, note):
    run_migration(db_engine, UP)
    with db_engine.begin() as connection:
        connection.execute(text("""
            UPDATE enrollment_events SET note = :note
            WHERE source = 'test-migration002'
        """), {"note": note})
    with db_engine.connect() as connection:
        values = connection.execute(text("""
            SELECT note FROM enrollment_events
            WHERE source = 'test-migration002' ORDER BY id
        """)).scalars().all()
    assert values == [note, note, note]
    assert old_rows(db_engine) == populated_events


def test_201_characters_fail_without_changing_rows(db_engine, populated_events):
    run_migration(db_engine, UP)
    with pytest.raises(DBAPIError) as error:
        with db_engine.begin() as connection:
            # Do not CAST to VARCHAR(200): an explicit cast can truncate text.
            connection.execute(text("""
                UPDATE enrollment_events SET note = :note
                WHERE source = 'test-migration002'
            """), {"note": "ộ" * 201})
    assert error.value.orig.sqlstate == "22001"
    assert old_rows(db_engine) == populated_events
    with db_engine.connect() as connection:
        assert connection.execute(text("""
            SELECT COUNT(*) FROM enrollment_events WHERE note IS NOT NULL
        """)).scalar_one() == 0


def test_duplicate_up_fails_without_partial_changes(db_engine, populated_events):
    run_migration(db_engine, UP)
    versions = migration_rows(db_engine)

    with pytest.raises(DBAPIError) as error:
        run_migration(db_engine, UP)

    assert error.value.orig.sqlstate == "42701"  # duplicate_column
    assert note_column(db_engine) == ("character varying", 200, "YES")
    assert old_rows(db_engine) == populated_events
    assert migration_rows(db_engine) == versions


def test_registry_failure_rolls_back_added_column(db_engine, populated_events):
    with db_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO schema_migrations (version, description)
            VALUES ('002', 'sentinel used only to test atomicity')
        """))
    versions = migration_rows(db_engine)

    with pytest.raises(DBAPIError) as error:
        run_migration(db_engine, UP)

    assert error.value.orig.sqlstate == "23505"  # duplicate migration version
    # ALTER TABLE succeeded first, but failed INSERT must undo that DDL.
    assert note_column(db_engine) is None
    assert migration_rows(db_engine) == versions
    assert old_rows(db_engine) == populated_events


def test_down_drops_note_but_preserves_old_rows(db_engine, populated_events):
    versions = migration_rows(db_engine)
    run_migration(db_engine, UP)
    with db_engine.begin() as connection:
        connection.execute(text("""
            UPDATE enrollment_events SET note = 'This value will be lost'
            WHERE source = 'test-migration002'
        """))

    run_migration(db_engine, DOWN)

    assert note_column(db_engine) is None
    assert old_rows(db_engine) == populated_events
    assert migration_rows(db_engine) == versions

    # Reapplying 002 recreates an empty note column; deleted notes do not return.
    run_migration(db_engine, UP)
    with db_engine.connect() as connection:
        assert connection.execute(text("""
            SELECT COUNT(*) FROM enrollment_events WHERE note IS NOT NULL
        """)).scalar_one() == 0


def test_duplicate_down_fails_without_partial_changes(db_engine, populated_events):
    run_migration(db_engine, UP)
    run_migration(db_engine, DOWN)
    versions = migration_rows(db_engine)

    with pytest.raises(DBAPIError) as error:
        run_migration(db_engine, DOWN)

    assert error.value.orig.sqlstate == "42703"  # undefined_column
    assert note_column(db_engine) is None
    assert old_rows(db_engine) == populated_events
    assert migration_rows(db_engine) == versions
