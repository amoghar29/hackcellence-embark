"""Booking helpers (inventory, seats, nights) shared with test_stateless_booking.py, which tests booking itself:
the Idempotency-Key header, one transaction, sold out, concurrency. Contract: docs/API.md, "2. Book".

conftest.restore_inventory puts the seats and rooms back after every test.
"""
import os
import uuid
from datetime import date, timedelta

import psycopg

from tests.test_api import package_body, search


def db():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


def nights(hotel):
    d, end = date.fromisoformat(hotel["start"][:10]), date.fromisoformat(hotel["end"][:10])
    while d < end:
        yield d
        d += timedelta(days=1)


def inventory(pkg):
    """({flight_id: seats_left}, {(room_id, night): rooms_left}) for what the package uses."""
    with db() as conn:
        seats = {i["catalog_id"]: conn.execute("SELECT seats_left FROM flights WHERE flight_id = %s",
                                               (i["catalog_id"],)).fetchone()[0]
                 for i in pkg["items"] if i["type"] == "flight"}
        rooms = {(i["room_id"], n): conn.execute("SELECT rooms_left FROM availability WHERE room_id = %s AND date = %s",
                                                 (i["room_id"], n)).fetchone()[0]
                 for i in pkg["items"] if i["type"] == "hotel" for n in nights(i)}
    return seats, rooms


def after_booking(pkg, before):
    seats, rooms = before
    return ({f: n - next(i["quantity"] for i in pkg["items"] if i.get("catalog_id") == f and i["type"] == "flight")
             for f, n in seats.items()},
            {(r, d): n - next(i["quantity"] for i in pkg["items"] if i["room_id"] == r) for (r, d), n in rooms.items()})


def set_seats(flight_id, n):
    with db() as conn:
        conn.execute("UPDATE flights SET seats_left = %s WHERE flight_id = %s", (n, flight_id))


def test_key_is_stored_on_the_booking_row(client):
    pkg = search(client)
    k = uuid.uuid4().hex
    r = client.post("/api/bookings", json=package_body(pkg), headers={"Idempotency-Key": k})
    assert r.status_code == 200, r.text
    with db() as conn:
        stored = conn.execute("SELECT idempotency_key FROM bookings WHERE reference = %s",
                              (r.json()["reference"],)).fetchone()
    assert stored[0] == k
