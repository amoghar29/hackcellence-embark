"""No trip_id: search saves nothing, the client sends {request, selection} back, and booking inserts every section
of the package in one transaction. Contract: docs/API.md.

conftest.restore_inventory puts the seats and rooms back after every test.
"""
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from tests.check_trip import check, load_catalog
from tests.test_api import MENON, assert_not_found, of_type, search
from tests.test_booking import after_booking, inventory, nights, set_seats

CAT = load_catalog()
SECTIONS = ("booking_flights", "booking_hotels", "booking_transfers", "booking_attractions")


def db():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


def count(table):
    with db() as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def rows():
    return {t: count(t) for t in ("bookings", *SECTIONS)}


def body(pkg):
    return {"request": pkg["request"], "selection": pkg["selection"]}


def book(client, pkg, k=None, payload=None):
    return client.post("/api/bookings", json=payload or body(pkg), headers={"Idempotency-Key": k or uuid.uuid4().hex})


# ---------- search keeps nothing ----------

def test_search_saves_nothing(client):
    before = rows()
    search(client)
    assert rows() == before


def test_results_saves_nothing(client):
    before = rows()
    r = client.post("/api/packages/results", json=MENON)
    assert r.status_code == 201 and r.json()["count"] > 1
    assert rows() == before


def test_package_has_no_trip_id_and_carries_what_booking_needs(client):
    pkg = search(client)
    assert "trip_id" not in pkg
    assert pkg["request"]["departure_city"] == "BLR" and pkg["request"]["nights"] == 6
    assert {"arrival", "return", "stays", "intercity", "attractions"} <= pkg["selection"].keys()
    assert pkg["status"] == "PLANNED" and pkg["reference"] is None


def test_same_request_gives_the_same_selection(client):
    assert search(client)["selection"] == search(client)["selection"]


def test_results_picks_index_the_packages(client):
    found = client.post("/api/packages/results", json=MENON).json()
    assert set(found["picks"]) == {"cheapest", "fastest", "best_rated"}
    pool = found["packages"]
    assert all(isinstance(n, int) and 0 <= n < len(pool) for n in found["picks"].values())
    assert pool[found["picks"]["cheapest"]]["total_inr"] == min(p["total_inr"] for p in pool)
    assert all("trip_id" not in p for p in pool)


@pytest.mark.parametrize("path", ["/api/packages/abc", "/api/packages/abc/days", "/api/packages/abc/flights"])
def test_id_routes_are_gone(client, path):
    assert_not_found(client.get(path))


# ---------- booking inserts every section in one transaction ----------

def test_book_returns_booked_package(client):
    pkg = search(client)
    r = book(client, pkg)
    assert r.status_code == 200, r.text
    ref, booked = r.json()["reference"], r.json()["package"]
    assert re.fullmatch(r"[1-9]\d{9}", ref)
    assert booked["status"] == "BOOKED" and booked["reference"] == ref and "trip_id" not in booked
    assert all(i["status"] == "BOOKED" and i["booking"] == {"reference": ref} for i in booked["items"])
    assert booked["total_inr"] == pkg["total_inr"]
    assert check(booked, CAT) == []


def test_each_section_is_a_row_linked_to_the_booking(client):
    pkg = search(client)
    before = rows()
    ref = book(client, pkg).json()["reference"]
    after = rows()
    assert after["bookings"] == before["bookings"] + 1
    assert after["booking_flights"] == before["booking_flights"] + len(of_type(pkg, "flight"))
    assert after["booking_hotels"] == before["booking_hotels"] + len(of_type(pkg, "hotel"))
    assert after["booking_transfers"] == before["booking_transfers"] + len(of_type(pkg, "transfer"))
    assert after["booking_attractions"] == before["booking_attractions"] + len(of_type(pkg, "attraction"))
    with db() as conn:
        b = conn.execute("SELECT arrival_flight_booking_id, return_flight_booking_id, arrival_transfer_booking_id, "
                         "return_transfer_booking_id, total_inr FROM bookings WHERE reference = %s", (ref,)).fetchone()
        assert None not in b and b[4] == pkg["total_inr"]
        for table, ids in (("booking_flights", b[0:2]), ("booking_transfers", b[2:4])):
            got = conn.execute(f"SELECT count(*) FROM {table} WHERE booking_id = %s AND id = ANY(%s)",
                               (ref, list(ids))).fetchone()[0]
            assert got == 2
        for t in SECTIONS:
            assert conn.execute(f"SELECT count(*) FROM {t} WHERE booking_id = %s", (ref,)).fetchone()[0] > 0 or t == "booking_attractions"


def test_booking_takes_seats_and_rooms(client):
    pkg = search(client)
    before = inventory(pkg)
    assert book(client, pkg).status_code == 200
    assert inventory(pkg) == after_booking(pkg, before)


def test_same_key_and_package_replays(client):
    pkg = search(client)
    k = uuid.uuid4().hex
    first = book(client, pkg, k)
    taken, made = inventory(pkg), rows()
    second = book(client, pkg, k)
    assert second.status_code == 200 and second.json() == first.json()
    assert inventory(pkg) == taken and rows() == made


def test_same_key_for_another_package_is_refused(client):
    a, b = search(client), search(client, dict(MENON, nights=5))
    k = uuid.uuid4().hex
    assert book(client, a, k).status_code == 200
    made, seats = rows(), inventory(b)
    r = book(client, b, k)
    assert r.status_code == 409 and r.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert rows() == made and inventory(b) == seats


def test_new_key_books_the_package_again(client):
    pkg = search(client)
    first = book(client, pkg).json()["reference"]
    second = book(client, pkg).json()["reference"]
    assert first != second


def test_concurrent_bookings_with_one_key_book_once(client):
    pkg = search(client)
    before, made = inventory(pkg), rows()
    k = uuid.uuid4().hex
    with ThreadPoolExecutor(4) as pool:
        responses = list(pool.map(lambda _: book(client, pkg, k), range(4)))
    assert {r.status_code for r in responses} == {200}
    assert len({r.json()["reference"] for r in responses}) == 1
    assert inventory(pkg) == after_booking(pkg, before)
    assert rows()["bookings"] == made["bookings"] + 1


def test_concurrent_bookings_of_the_last_seats_book_one(client):
    pkg = search(client)
    flight = next(i for i in pkg["items"] if i["item_id"] == "flight-arrival")
    set_seats(flight["catalog_id"], flight["quantity"])
    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(lambda _: book(client, pkg).status_code, range(2)))
    assert codes == [200, 409]
    assert inventory(pkg)[0][flight["catalog_id"]] == 0


# ---------- sold out: nothing is written, nothing is taken ----------

def test_sold_out_room_writes_nothing(client):
    pkg = search(client)
    hotel = of_type(pkg, "hotel")[-1]
    with db() as conn:
        conn.execute("UPDATE availability SET rooms_left = 0 WHERE room_id = %s AND date = %s",
                     (hotel["room_id"], list(nights(hotel))[-1]))
    before, made = inventory(pkg), rows()
    r = book(client, pkg)
    assert r.status_code == 409 and r.json()["code"] == "SOLD_OUT" and r.json()["part"] == "hotel"
    assert inventory(pkg) == before and rows() == made


def test_sold_out_return_flight_writes_nothing(client):
    pkg = search(client)
    set_seats(next(i for i in pkg["items"] if i["item_id"] == "flight-return")["catalog_id"], 0)
    before, made = inventory(pkg), rows()
    r = book(client, pkg)
    assert r.status_code == 409 and r.json()["code"] == "SOLD_OUT" and r.json()["part"] == "flight"
    assert inventory(pkg) == before and rows() == made


def test_key_of_a_sold_out_attempt_can_retry(client):
    pkg = search(client)
    flight = next(i for i in pkg["items"] if i["item_id"] == "flight-arrival")
    seats = inventory(pkg)[0][flight["catalog_id"]]
    set_seats(flight["catalog_id"], 0)
    k = uuid.uuid4().hex
    assert book(client, pkg, k).status_code == 409
    set_seats(flight["catalog_id"], seats)
    assert book(client, pkg, k).status_code == 200


def test_a_failing_insert_rolls_back_inventory(client, monkeypatch):
    """Everything is one transaction: if a section cannot be written, the seats and rooms are not taken either."""
    from app.repositories import package_repo

    pkg = search(client)
    before, made = inventory(pkg), rows()

    def boom(*a, **kw):
        raise RuntimeError("disk full")

    monkeypatch.setattr(package_repo.PackageRepository, "_insert_parts", staticmethod(boom))
    with pytest.raises(RuntimeError):
        book(client, pkg)
    assert inventory(pkg) == before and rows() == made


# ---------- bad input ----------

def test_book_without_key_is_invalid(client):
    r = client.post("/api/bookings", json=body(search(client)))
    assert r.status_code == 400 and r.json()["field"] == "Idempotency-Key"


@pytest.mark.parametrize("k", ["", "k" * 256])
def test_book_with_bad_key_is_invalid(client, k):
    r = client.post("/api/bookings", json=body(search(client)), headers={"Idempotency-Key": k})
    assert r.status_code == 400 and r.json()["field"] == "Idempotency-Key"


@pytest.mark.parametrize("payload", [None, [], {}, {"request": {}}, {"selection": {}}])
def test_book_without_a_package_is_invalid(client, payload):
    made = rows()
    r = client.post("/api/bookings", json=payload, headers={"Idempotency-Key": uuid.uuid4().hex})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_REQUEST"
    assert rows() == made


def tampered(pkg, edit):
    p = body(pkg)
    edit(p["selection"])
    return p


TAMPERED = {
    "unknown_flight": lambda s: s["arrival"].update(flight_id="FL-NOPE"),
    "unknown_hotel": lambda s: s["stays"][0].update(hotel_id="HTL-NOPE"),
    "flight_of_another_day": lambda s: s["return"].update(flight_id="FL-711"),
    "no_stays": lambda s: s.update(stays=[]),
    "stay_dates_moved": lambda s: s["stays"][0].update(check_out="2027-04-30"),
    "attraction_twice": lambda s: s["attractions"].append(dict(s["attractions"][0])),
    "bad_time": lambda s: s["arrival"].update(pickup="not a time"),
}


@pytest.mark.parametrize("edit", TAMPERED.values(), ids=TAMPERED.keys())
def test_tampered_selection_is_refused_and_writes_nothing(client, edit):
    pkg = search(client)
    made, seats = rows(), inventory(pkg)
    r = book(client, pkg, payload=tampered(pkg, edit))
    assert r.status_code == 400 and r.json()["code"] == "INVALID_REQUEST", r.text
    assert rows() == made and inventory(pkg) == seats


def test_the_client_cannot_set_a_price(client):
    pkg = search(client)
    payload = dict(body(pkg), total_inr=1, items=[])
    r = book(client, pkg, payload=payload)
    assert r.status_code == 200 and r.json()["package"]["total_inr"] == pkg["total_inr"]


# ---------- reservations are read from the booking rows ----------

def test_reservation_opens_the_booked_package(client):
    booked = book(client, search(client)).json()
    r = client.get(f"/api/reservations/{booked['reference']}")
    assert r.status_code == 200 and r.json() == booked["package"]


def test_my_bookings_lists_newest_first(client):
    first, second = book(client, search(client)).json(), book(client, search(client, dict(MENON, nights=5))).json()
    refs = [r["reference"] for r in client.get("/api/reservations").json()["reservations"]]
    assert refs[:2] == [second["reference"], first["reference"]]


@pytest.mark.parametrize("ref", ["0000000000", "9999999999", "123", "abcdefghij"])
def test_wrong_reservation_number_not_found(client, ref):
    assert_not_found(client.get(f"/api/reservations/{ref}"))


# ---------- changing a package without saving it ----------

def test_hotel_options_and_change_work_on_the_package_sent(client):
    pkg = search(client)
    before = rows()
    city = of_type(pkg, "hotel")[0]["city"]
    r = client.post("/api/packages/options/hotels", json=dict(body(pkg), city=city))
    assert r.status_code == 200, r.text
    options = r.json()["options"]
    assert "trip_id" not in r.json() and options
    other = next(o for o in options if o["hotel_id"] != of_type(pkg, "hotel")[0]["catalog_id"])
    r = client.post("/api/packages/change", json=dict(body(pkg), change={
        "action": "change_hotel", "city": city, "hotel_id": other["hotel_id"], "room_id": other["room_id"]}))
    assert r.status_code == 200, r.text
    changed = r.json()
    assert of_type(changed, "hotel")[0]["catalog_id"] == other["hotel_id"]
    assert changed["selection"] != pkg["selection"] and "notices" in changed
    assert check({k: v for k, v in changed.items() if k != "notices"}, CAT) == []
    assert rows() == before
    assert book(client, changed).status_code == 200  # the changed package books as it is


def test_flight_attraction_and_city_plan_options(client):
    pkg = search(client)
    day = of_type(pkg, "hotel")[0]["start"]
    assert client.post("/api/packages/options/flights", json=dict(body(pkg), direction="RETURN")).status_code == 200
    assert client.post("/api/packages/options/attractions", json=dict(body(pkg), date=day)).status_code == 200
    r = client.post("/api/packages/options/city-plans", json=body(pkg))
    assert r.status_code == 200 and any(o["is_current"] for o in r.json()["options"])


def test_refused_change_says_why_and_changes_nothing(client):
    pkg = search(client)
    r = client.post("/api/packages/change", json=dict(body(pkg), change={
        "action": "change_hotel", "city": "Atlantis", "hotel_id": "x", "room_id": "y"}))
    assert r.status_code == 422 and r.json()["code"] == "CHANGE_REFUSED"


def test_change_needs_a_package(client):
    r = client.post("/api/packages/change", json={"change": {"action": "remove_attraction", "item_id": "x"}})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_REQUEST"
