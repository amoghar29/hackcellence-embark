"""M6 on a booked trip: open a reservation, change it with POST /api/packages/change, then save it with
PUT /api/reservations/{reference}. The old seats and rooms go back, the new ones are taken, all in one transaction.
"""
from tests.test_api import key, package_body
from tests.test_api_changes import CAT, MENON, change, rooms_ok, stay
from tests.test_booking import db, inventory, set_seats


def booked(client):
    pkg = client.post("/api/packages/search", json=MENON).json()
    r = client.post("/api/bookings", json=package_body(pkg), headers=key())
    assert r.status_code == 200, r.text
    return r.json()["reference"]


def reopen(client, ref):
    r = client.get(f"/api/reservations/{ref}")
    assert r.status_code == 200, r.text
    return r.json()


def other_hotel(pkg):
    h, city, ci, co = stay(pkg)
    room = next(r for r in CAT["rooms"].values() if CAT["hotels"][r["hotel_id"]]["city"] == city
                and r["hotel_id"] != h["catalog_id"] and r["max_adults"] >= 2 and r["max_children"] >= 1
                and rooms_ok(r, 1, ci, co))
    return {"action": "change_hotel", "city": city, "hotel_id": room["hotel_id"], "room_id": room["room_id"]}


def save(client, ref, pkg):
    return client.put(f"/api/reservations/{ref}", json=package_body(pkg))


def test_reservation_carries_request_and_selection(client):
    pkg = reopen(client, booked(client))
    assert pkg["status"] == "BOOKED"
    assert pkg["request"]["departure_city"] == "BLR" and "stays" in pkg["selection"]


def test_modify_saves_the_changed_package(client):
    ref = booked(client)
    old = reopen(client, ref)
    status, new = change(client, old, other_hotel(old))
    assert status == 200
    r = save(client, ref, new)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["reference"] == ref and got["status"] == "BOOKED"
    assert got["total_inr"] == new["total_inr"]
    assert reopen(client, ref)["selection"] == new["selection"]


def test_modify_returns_old_inventory_and_takes_new(client):
    ref = booked(client)
    old = reopen(client, ref)
    _, new = change(client, old, other_hotel(old))
    old_before, new_before = inventory(old), inventory(new)
    assert save(client, ref, new).status_code == 200
    old_after, new_after = inventory(old), inventory(new)
    old_room = stay(old)[0]["room_id"]
    new_room = stay(new)[0]["room_id"]
    for (room, night), n in old_before[1].items():
        if room == old_room:
            assert old_after[1][(room, night)] == n + 1   # given back
    for (room, night), n in new_before[1].items():
        if room == new_room:
            assert new_after[1][(room, night)] == n - 1   # taken
    assert old_after[0] == old_before[0]  # flights unchanged


def test_modify_when_new_room_is_sold_out_changes_nothing(client):
    ref = booked(client)
    old = reopen(client, ref)
    _, new = change(client, old, other_hotel(old))
    h = stay(new)[0]
    with db() as conn:
        conn.execute("UPDATE availability SET rooms_left = 0 WHERE room_id = %s AND date = %s",
                     (h["room_id"], h["start"][:10]))
    before = inventory(old)
    r = save(client, ref, new)
    assert r.status_code == 409 and r.json()["code"] == "SOLD_OUT"
    assert reopen(client, ref)["selection"] == old["selection"]
    assert inventory(old) == before


def test_keeping_the_same_flight_is_never_sold_out_to_itself(client):
    ref = booked(client)
    old = reopen(client, ref)
    _, new = change(client, old, other_hotel(old))
    for f in (i for i in new["items"] if i["type"] == "flight"):
        set_seats(f["catalog_id"], 0)  # the booking already holds its own seats
    assert save(client, ref, new).status_code == 200


def test_modify_unknown_reservation_is_not_found(client):
    pkg = client.post("/api/packages/search", json=MENON).json()
    r = client.put("/api/reservations/1234567890", json=package_body(pkg))
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_modify_cannot_change_dates_or_travelers(client):
    ref = booked(client)
    old = reopen(client, ref)
    body = package_body(old)
    body["request"] = {**body["request"], "adults": 3}
    r = client.put(f"/api/reservations/{ref}", json=body)
    assert r.status_code == 400 and r.json()["field"] == "request"  # INVALID_REQUEST, docs/API.md


def test_changing_a_booking_counts_its_own_seats_and_rooms_as_free(client):
    ref = booked(client)
    old = reopen(client, ref)
    for f in (i for i in old["items"] if i["type"] == "flight"):
        set_seats(f["catalog_id"], 0)  # every other seat is gone; the booking still holds its own
    hotel = other_hotel(old)
    r = client.post("/api/packages/change", json=dict(package_body(old), reference=ref, change=hotel))
    assert r.status_code == 200, r.text
    assert client.post("/api/packages/change", json=dict(package_body(old), change=hotel)).status_code == 422
    flights = client.post("/api/packages/options/flights", json=dict(package_body(old), reference=ref, direction="ARRIVAL"))
    assert flights.status_code == 200 and flights.json()["options"]
