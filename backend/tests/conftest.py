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
    # The first run snapshots the seeded inventory; booking takes seats and rooms, so each test puts them back.
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS seed_flights AS SELECT flight_id, seats_left FROM flights")
        conn.execute("CREATE TABLE IF NOT EXISTS seed_availability AS "
                     "SELECT room_id, date, rooms_left FROM availability")


@pytest.fixture(autouse=True)
def restore_inventory(seeded_db):
    yield
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        conn.execute("UPDATE flights f SET seats_left = s.seats_left FROM seed_flights s "
                     "WHERE f.flight_id = s.flight_id AND f.seats_left <> s.seats_left")
        conn.execute("UPDATE availability a SET rooms_left = s.rooms_left FROM seed_availability s "
                     "WHERE a.room_id = s.room_id AND a.date = s.date AND a.rooms_left <> s.rooms_left")


@pytest.fixture
def cat(seeded_db):
    """The catalog repository on its own connection. Whatever a test changes in the tables is rolled back."""
    from app.core import db
    from app.repositories.catalog_repo import CatalogRepository

    with db.connect() as conn:
        yield CatalogRepository(conn)
        conn.rollback()


@pytest.fixture
def menon_request():
    return dict(MENON_REQUEST, child_ages=list(MENON_REQUEST["child_ages"]))


@pytest.fixture
def menon_trip():
    """A hand-built valid Menon package (Tokyo 3 nights, Kyoto 3 nights); items listed in tests/mutations.py."""
    with open(FIXTURES / "menon_trip.json", encoding="utf-8") as f:
        return copy.deepcopy(json.load(f))


@pytest.fixture
def client(seeded_db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
