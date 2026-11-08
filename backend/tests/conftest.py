from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.tests.support import isolated_database, source_state


@pytest.fixture(scope="session", autouse=True)
def verify_source_preserved():
    before = source_state()
    yield
    after = source_state()
    preserved = before == after
    if os.getenv("COURSEHUB_TEST_REPORT"):
        target = Path(os.environ["COURSEHUB_TEST_REPORT"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "source_preserved": preserved,
            "before": before,
            "after": after,
            "method": "Disposable schema per test; fingerprint source rows, columns, indexes, sequences",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    assert preserved, "Source schema differs after integration tests"


@pytest.fixture
def db_engine():
    with isolated_database() as engine:
        yield engine


@pytest.fixture
def client(db_engine, monkeypatch):
    from backend.app import main
    monkeypatch.setattr(main, "engine", db_engine)
    with TestClient(main.app) as test_client:
        yield test_client
