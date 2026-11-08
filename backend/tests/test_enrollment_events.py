from sqlalchemy import text
import pytest


@pytest.fixture
def event_ids(db_engine):
    with db_engine.begin() as connection:
        return list(connection.execute(text("""
            INSERT INTO enrollment_events
                (student_id, class_section_id, event_type, source, occurred_at)
            VALUES
                ('22000001', 'WEB-01', 'CREATED', 'test-bai1', '2026-11-01 10:00:00'),
                ('22000001', 'WEB-01', 'CANCELLED', 'test-bai1', '2026-11-02 10:00:00'),
                ('22000001', 'WEB-02', 'CREATED', 'test-bai1', '2026-11-02 10:00:00'),
                ('22000002', 'WEB-02', 'CREATED', 'test-bai1', '2026-11-03 10:00:00')
            RETURNING id
        """)).scalars())


def test_default_order_and_combined_filters(client, event_ids):
    response = client.get("/enrollment-events")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == list(reversed(event_ids))
    response = client.get("/enrollment-events", params={
        "student_id": "22000001", "event_type": "CREATED",
    })
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [event_ids[2], event_ids[0]]


def test_filter_event_type_alone(client, event_ids):
    response = client.get("/enrollment-events", params={"event_type": "CANCELLED"})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [event_ids[1]]


def test_tied_timestamps_and_pages(client, event_ids):
    params = {"student_id": "22000001", "limit": 1}
    pages = [client.get("/enrollment-events", params={**params, "skip": skip})
             for skip in range(4)]
    assert all(response.status_code == 200 for response in pages)
    assert [response.json()[0]["id"] for response in pages[:3]] == list(reversed(event_ids[:3]))
    assert pages[3].json() == []


@pytest.mark.parametrize("limit", [1, 100])
def test_limit_boundaries(client, event_ids, limit):
    response = client.get("/enrollment-events", params={"limit": limit})
    assert response.status_code == 200
    assert len(response.json()) == min(limit, len(event_ids))


def test_empty_results(client, event_ids):
    response = client.get("/enrollment-events", params={"student_id": "99999999"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"limit": "abc"},
    {"skip": -1}, {"skip": "abc"}, {"event_type": "INVALID"},
    {"student_id": "1"}, {"student_id": "123456789"},
    {"event_type": "CREATED' OR 1=1 --"},
])
def test_invalid_query(client, params):
    assert client.get("/enrollment-events", params=params).status_code == 422


def test_student_value_is_bound(client, event_ids):
    # Eight characters pass field length validation but are still treated as data.
    response = client.get("/enrollment-events", params={"student_id": "' OR 1=1"})
    assert response.status_code == 200
    assert response.json() == []
