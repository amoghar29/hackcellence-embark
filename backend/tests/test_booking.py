"""Booking: the Idempotency-Key header, and taking seats and rooms in one transaction. Contract: docs/API.md, "2. Book".

conftest.restore_inventory puts the seats and rooms back after every test.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import psycopg

from tests.test_api import assert_not_found, search


def db():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


def key():
    return uuid.uuid4().hex


def book(client, trip_id, k):
    return client.post(f"/api/packages/{trip_id}/book", headers={"Idempotency-Key": k})


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


def status(client, pkg):
    return client.get(f"/api/packages/{pkg['trip_id']}").json()["status"]


# ---------- the header ----------

def test_book_without_key_is_invalid(client):
    pkg = search(client)
    r = client.post(f"/api/packages/{pkg['trip_id']}/book")
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_REQUEST" and r.json()["field"] == "Idempotency-Key"
    assert status(client, pkg) == "PLANNED"


def test_book_with_empty_key_is_invalid(client):
    r = book(client, search(client)["trip_id"], "")
    assert r.status_code == 400 and r.json()["field"] == "Idempotency-Key"


def test_book_with_too_long_key_is_invalid(client):
    r = book(client, search(client)["trip_id"], "k" * 256)
    assert r.status_code == 400 and r.json()["field"] == "Idempotency-Key"


def test_unknown_package_with_key_not_found(client):
    assert_not_found(book(client, "does-not-exist", key()))


# ---------- inventory ----------

def test_booking_takes_seats_and_rooms(client):
    pkg = search(client)
    before = inventory(pkg)
    r = book(client, pkg["trip_id"], key())
    assert r.status_code == 200, r.text
    assert inventory(pkg) == after_booking(pkg, before)


def test_same_key_replays_without_taking_again(client):
    pkg = search(client)
    k = key()
    first = book(client, pkg["trip_id"], k)
    taken = inventory(pkg)
    second = book(client, pkg["trip_id"], k)
    assert second.status_code == 200 and second.json() == first.json()
    assert inventory(pkg) == taken


def test_new_key_on_booked_package_keeps_reference_and_inventory(client):
    pkg = search(client)
    first = book(client, pkg["trip_id"], key()).json()["reference"]
    taken = inventory(pkg)
    r = book(client, pkg["trip_id"], key())
    assert r.status_code == 200 and r.json()["reference"] == first
    assert inventory(pkg) == taken


def test_key_reused_for_another_package_is_refused(client):
    a, b = search(client), search(client)
    k = key()
    assert book(client, a["trip_id"], k).status_code == 200
    before = inventory(b)
    r = book(client, b["trip_id"], k)
    assert r.status_code == 409 and r.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert status(client, b) == "PLANNED"
    assert inventory(b) == before


# ---------- sold out: nothing is taken ----------

def test_sold_out_room_rolls_back_everything(client):
    pkg = search(client)
    hotel = [i for i in pkg["items"] if i["type"] == "hotel"][-1]
    with db() as conn:
        conn.execute("UPDATE availability SET rooms_left = 0 WHERE room_id = %s AND date = %s",
                     (hotel["room_id"], list(nights(hotel))[-1]))
    before = inventory(pkg)
    r = book(client, pkg["trip_id"], key())
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "SOLD_OUT" and body["part"] == "hotel" and body["error"]
    assert inventory(pkg) == before  # the flights and the other nights were not taken either
    assert status(client, pkg) == "PLANNED"


def test_sold_out_return_flight_rolls_back_everything(client):
    pkg = search(client)
    set_seats(next(i for i in pkg["items"] if i["item_id"] == "flight-return")["catalog_id"], 0)
    before = inventory(pkg)
    r = book(client, pkg["trip_id"], key())
    assert r.status_code == 409
    assert r.json()["code"] == "SOLD_OUT" and r.json()["part"] == "flight"
    assert inventory(pkg) == before
    assert status(client, pkg) == "PLANNED"


def test_key_of_a_sold_out_attempt_can_retry(client):
    pkg = search(client)
    flight = next(i for i in pkg["items"] if i["item_id"] == "flight-arrival")
    seats = inventory(pkg)[0][flight["catalog_id"]]
    set_seats(flight["catalog_id"], 0)
    k = key()
    assert book(client, pkg["trip_id"], k).status_code == 409
    set_seats(flight["catalog_id"], seats)
    r = book(client, pkg["trip_id"], k)
    assert r.status_code == 200 and r.json()["package"]["status"] == "BOOKED"


# ---------- concurrency ----------

def test_concurrent_bookings_with_one_key_take_inventory_once(client):
    pkg = search(client)
    before = inventory(pkg)
    k = key()
    with ThreadPoolExecutor(4) as pool:
        responses = list(pool.map(lambda _: book(client, pkg["trip_id"], k), range(4)))
    assert {r.status_code for r in responses} == {200}
    assert len({r.json()["reference"] for r in responses}) == 1
    assert inventory(pkg) == after_booking(pkg, before)


def test_concurrent_bookings_of_the_last_seats_book_one(client):
    """Two packages on the same flight with seats for only one: one books, the other is SOLD_OUT."""
    a, b = search(client), search(client)
    flight = next(i for i in a["items"] if i["item_id"] == "flight-arrival")
    assert flight["catalog_id"] == next(i for i in b["items"] if i["item_id"] == "flight-arrival")["catalog_id"]
    set_seats(flight["catalog_id"], flight["quantity"])
    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(lambda p: book(client, p["trip_id"], key()).status_code, (a, b)))
    assert codes == [200, 409]
    assert inventory(a)[0][flight["catalog_id"]] == 0


# ---------- where the key lives ----------

def test_key_is_stored_on_the_booking_row(client):
    pkg = search(client)
    k = key()
    with db() as conn:
        assert conn.execute("SELECT idempotency_key FROM bookings WHERE id = %s", (pkg["trip_id"],)).fetchone()[0] is None
    assert book(client, pkg["trip_id"], k).status_code == 200
    with db() as conn:
        assert conn.execute("SELECT idempotency_key FROM bookings WHERE id = %s", (pkg["trip_id"],)).fetchone()[0] == k
