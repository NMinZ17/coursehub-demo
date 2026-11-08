"""Real PostgreSQL tests: valid commit and failure of the second table write."""

import hashlib
import json

from fastapi.testclient import TestClient
from sqlalchemy import event, text

from backend.tests.rollback_demo import create_demo_app


PAYLOAD = {"student_id": "22000004", "class_section_id": "WEB-02"}


def snapshot(engine):
    """Read committed state using a separate connection after each HTTP request."""
    result = {}
    with engine.connect() as connection:
        for table, order in (
            ("enrollments", "student_id, class_section_id"),
            ("enrollment_events", "id"),
        ):
            rows = [
                dict(row)
                for row in connection.execute(
                    text(f"SELECT * FROM {table} ORDER BY {order}")
                ).mappings()
            ]
            digest = hashlib.sha256(
                json.dumps(rows, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            result[table] = {"count": len(rows), "digest": digest}
    return result


def test_invalid_event_rolls_back_both_tables(db_engine):
    before = snapshot(db_engine)
    completed = []
    attempted = []

    def after_execute(connection, cursor, statement, parameters, context, many):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("insert into enrollments "):
            completed.append("enrollments")

    def before_execute(connection, cursor, statement, parameters, context, many):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("insert into enrollment_events "):
            attempted.append("enrollment_events")

    event.listen(db_engine, "after_cursor_execute", after_execute)
    event.listen(db_engine, "before_cursor_execute", before_execute)
    try:
        with TestClient(create_demo_app(db_engine)) as demo_client:
            response = demo_client.post(
                "/demo/enrollments", json={**PAYLOAD, "event_type": "INVALID"}
            )
    finally:
        event.remove(db_engine, "after_cursor_execute", after_execute)
        event.remove(db_engine, "before_cursor_execute", before_execute)

    assert completed == ["enrollments"]
    assert attempted == ["enrollment_events"]
    assert response.status_code == 409
    assert response.json()["detail"]["constraint"] == "ck_enrollment_events_type"
    assert response.json()["detail"]["sqlstate"] == "23514"
    assert snapshot(db_engine) == before

    with db_engine.connect() as connection:
        assert connection.execute(
            text("""
                SELECT COUNT(*) FROM enrollments
                WHERE student_id = :student_id
                  AND class_section_id = :class_section_id
            """),
            PAYLOAD,
        ).scalar_one() == 0


def test_valid_event_commits_both_tables(db_engine):
    before = snapshot(db_engine)
    with TestClient(create_demo_app(db_engine)) as demo_client:
        response = demo_client.post(
            "/demo/enrollments", json={**PAYLOAD, "event_type": "CREATED"}
        )

    assert response.status_code == 201
    after = snapshot(db_engine)
    for table in ("enrollments", "enrollment_events"):
        assert after[table]["count"] == before[table]["count"] + 1

    with db_engine.connect() as connection:
        row = connection.execute(
            text("""
                SELECT e.student_id, e.class_section_id, ee.event_type
                FROM enrollments AS e
                JOIN enrollment_events AS ee
                  ON ee.student_id = e.student_id
                 AND ee.class_section_id = e.class_section_id
                WHERE e.student_id = :student_id
                  AND e.class_section_id = :class_section_id
                  AND ee.source = 'rollback-test'
            """),
            PAYLOAD,
        ).mappings().one()
    assert dict(row) == {**PAYLOAD, "event_type": "CREATED"}


def test_production_app_has_no_demo_endpoint(client):
    assert client.post("/demo/enrollments", json=PAYLOAD).status_code == 404
    assert "/demo/enrollments" not in client.get("/openapi.json").json()["paths"]
