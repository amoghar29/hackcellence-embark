import copy
import json
import os
from pathlib import Path

import pytest

# Tests use their own database so they never touch the dev data.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://embark:embark@localhost:5432/embark_test"
)

import psycopg  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

MENON_REQUEST = {
    "departure_city": "BLR",
    "country": "Japan",
    "start_date": "2027-04-10",
    "nights": 6,
    "adults": 2,
    "child_ages": [6],
    "budget_inr": 350000,
}


def _ensure_test_database():
    url = os.environ["DATABASE_URL"]
    base, name = url.rsplit("/", 1)
    with psycopg.connect(base + "/postgres", autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{name}"')


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    _ensure_test_database()
    from app.core import db, seed

    db.init_db()
    seed.seed()


@pytest.fixture(scope="session")
def cat(seeded_db):
    from app.repositories import catalog_repo

    return catalog_repo.load_catalog()


@pytest.fixture
def menon_request():
    return dict(MENON_REQUEST, child_ages=list(MENON_REQUEST["child_ages"]))


@pytest.fixture
def menon_trip():
    """A hand-built valid Menon package (Tokyo 3 nights, Kyoto 3 nights)."""
    with open(FIXTURES / "menon_trip.json", encoding="utf-8") as f:
        return copy.deepcopy(json.load(f))


@pytest.fixture
def client(seeded_db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
