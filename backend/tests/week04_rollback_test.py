from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.database import engine

SECTION_ID = "HW-ROLLBACK-01"
PARAMS = {"section_id": SECTION_ID, "student_id": "22000004"}


def counts(connection):
    return tuple(connection.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM enrollments
             WHERE class_section_id = :section_id) AS enrollments,
            (SELECT COUNT(*) FROM enrollment_events
             WHERE class_section_id = :section_id) AS events
    """), PARAMS).one())


def main():
    with engine.connect() as connection:
        exists = connection.execute(text("""
            SELECT 1 FROM class_sections WHERE id = :section_id
        """), PARAMS).first()
        assert exists is None, "Lop thu da ton tai; hay doi SECTION_ID."
        before = counts(connection)
        assert before == (0, 0)
    print("Truoc test (enrollments, events):", before)

    try:
        with engine.begin() as connection:
            # This test-only class is also rolled back.
            section = connection.execute(text("""
                INSERT INTO class_sections
                    (id, course_code, semester_code, lecturer_id, capacity)
                SELECT :section_id, course_code, semester_code, lecturer_id, 1
                FROM class_sections WHERE id = 'WEB-01'
                RETURNING id
            """), PARAMS).first()
            assert section is not None, "Thieu lop mau WEB-01."

            connection.execute(text("""
                INSERT INTO enrollments (student_id, class_section_id)
                VALUES (:student_id, :section_id)
            """), PARAMS)
            assert counts(connection) == (1, 0)
            print("Trong transaction: da INSERT enrollments, counts = (1, 0)")

            connection.execute(text("""
                INSERT INTO enrollment_events
                    (student_id, class_section_id, event_type, source, dataset)
                VALUES (:student_id, :section_id, 'INVALID', 'hw02-test', 'demo')
            """), PARAMS)

            # If the CHECK is missing, this exception still rolls back setup.
            raise AssertionError("FAIL: event_type INVALID khong bi tu choi.")

    except IntegrityError as exc:
        # Verify the intended CHECK failed, rather than a PK or FK.
        if (
            exc.orig.sqlstate != "23514"
            or exc.orig.diag.constraint_name != "ck_enrollment_events_type"
        ):
            raise
        print("Da gap dung loi CHECK event_type; transaction da rollback.")

    with engine.connect() as connection:
        after = counts(connection)
        assert after == before == (0, 0), (before, after)
        assert connection.execute(text("""
            SELECT 1 FROM class_sections WHERE id = :section_id
        """), PARAMS).first() is None

    print("Sau test (enrollments, events):", after)
    print("PASS: hai bang khong tang; lop thu cung da duoc rollback.")


if __name__ == "__main__":
    main()