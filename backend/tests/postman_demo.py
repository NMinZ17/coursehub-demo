"""Serve deterministic Bài 1 fixtures inside a disposable PostgreSQL schema.

Run: python -m backend.tests.postman_demo --port 8011
Stop gracefully with Ctrl+C so the schema and its identity sequence are removed.
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager

from sqlalchemy import text
import uvicorn

# Load connection configuration before importing the production app module.
from backend.tests.support import isolated_database
from backend.app import main as application


def make_demo_app():
    """Wrap production lifespan so cleanup precedes Uvicorn's signal replay."""
    app = application.app
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def demo_lifespan(running_app):
        original_engine = application.engine
        try:
            with isolated_database() as db_engine:
                try:
                    with db_engine.begin() as connection:
                        ids = connection.execute(text("""
                            INSERT INTO enrollment_events
                                (student_id, class_section_id, event_type,
                                 source, dataset, occurred_at)
                            VALUES
                                ('22000001', 'WEB-01', 'CREATED',
                                 'postman-bai1', 'demo',
                                 TIMESTAMP '2026-11-01 00:00:00'),
                                ('22000001', 'WEB-01', 'CANCELLED',
                                 'postman-bai1', 'demo',
                                 TIMESTAMP '2026-11-02 00:00:00'),
                                ('22000001', 'WEB-01', 'CREATED',
                                 'postman-bai1', 'demo',
                                 TIMESTAMP '2026-11-02 00:00:00')
                            RETURNING id
                        """)).scalars().all()
                        assert ids == [1, 2, 3], (
                            "Postman fixture must have deterministic IDs"
                        )

                    application.engine = db_engine
                    async with original_lifespan(running_app) as state:
                        yield state
                finally:
                    application.engine = original_engine

            # The schema and its sequence have been removed, and the original
            # database snapshot has compared equal, before shutdown completes.
            print("POSTMAN_DEMO_CLEANUP_CONFIRMED", flush=True)
        finally:
            app.router.lifespan_context = original_lifespan

    app.router.lifespan_context = demo_lifespan
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(
        make_demo_app(), host="127.0.0.1", port=args.port, reload=False,
    )


if __name__ == "__main__":
    main()
