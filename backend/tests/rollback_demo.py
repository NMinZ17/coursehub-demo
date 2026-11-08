"""Test-only transaction demo. Never import this module into the production app."""

from fastapi import FastAPI, HTTPException
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from backend.app.schemas import EnrollmentCreate


class DemoEnrollmentCreate(EnrollmentCreate):
    # Deliberately not Literal: the invalid value must reach the DB constraint.
    event_type: str = "CREATED"


def create_demo_app(test_engine: Engine) -> FastAPI:
    """Build an isolated app against the caller's disposable test engine."""
    demo = FastAPI(title="CourseHub rollback test demo")

    @demo.post("/demo/enrollments", status_code=201)
    def create_demo_enrollment(payload: DemoEnrollmentCreate) -> dict[str, str]:
        parameters = payload.model_dump()

        try:
            with test_engine.begin() as connection:
                connection.execute(
                    text("""
                        INSERT INTO enrollments (student_id, class_section_id)
                        VALUES (:student_id, :class_section_id)
                    """),
                    parameters,
                )
                connection.execute(
                    text("""
                        INSERT INTO enrollment_events
                            (student_id, class_section_id, event_type,
                             source, dataset)
                        VALUES
                            (:student_id, :class_section_id, :event_type,
                             'rollback-test', 'demo')
                    """),
                    parameters,
                )
        except IntegrityError as exc:
            # This handler runs after engine.begin() has rolled back both writes.
            constraint = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            )
            sqlstate = getattr(exc.orig, "sqlstate", None)
            if constraint != "ck_enrollment_events_type" or sqlstate != "23514":
                raise
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Event CHECK failed; both inserts rolled back",
                    "constraint": constraint,
                    "sqlstate": sqlstate,
                },
            ) from exc

        return {
            "message": "Enrollment and event committed",
            "student_id": payload.student_id,
            "class_section_id": payload.class_section_id,
        }

    return demo
