"""G1: a change that affects another booking is fixed (with a notice) or warned about, not just refused.

Nothing is saved: each call sends the package's request and selection and gets the new package back.
"""
from tests.check_trip import check, load_catalog
from tests.test_api import package_body

CAT = load_catalog()
MENON = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}


def new_package(client):
    r = client.post("/api/packages/search", json=MENON)
    assert r.status_code == 201, r.text
    return r.json()


def item(trip, item_id):
    return next(i for i in trip["items"] if i["item_id"] == item_id)


def flight_options(client, trip):
    r = client.post("/api/packages/options/flights", json=dict(package_body(trip), direction="ARRIVAL"))
    assert r.status_code == 200, r.text
    return r.json()["options"]


def patch(client, trip, change):
    return client.post("/api/packages/change", json=dict(package_body(trip), change=change))


def change_arrival(client, trip, flight_id):
    return patch(client, trip, {"action": "change_flight", "item_id": "flight-arrival", "flight_id": flight_id})


def test_change_always_returns_notices(client):
    trip = new_package(client)
    r = change_arrival(client, trip, flight_options(client, trip)[0]["flight_id"])
    assert r.status_code == 200 and isinstance(r.json()["notices"], list)


def test_later_arrival_drops_the_visit_it_would_miss_and_says_so(client):
    fixed = 0
    for opt in flight_options(client, new_package(client)):
        with_visit = new_package(client)  # the builder already plans a visit on an arrival day it can reach in time
        a = next((i for i in with_visit["items"] if i["type"] == "attraction" and i["start"][:10] == with_visit["start_date"]), None)
        if not a:
            continue
        r = change_arrival(client, with_visit, opt["flight_id"])
        body = r.json()
        assert r.status_code == 200, f"a visit that no longer fits must be removed, not refuse the flight: {body}"
        assert check({k: v for k, v in body.items() if k != "notices"}, CAT, first_package=False) == []
        if not any(i["item_id"] == a["item_id"] for i in body["items"]):
            fixed += 1
            assert any(n["level"] == "FIXED" and a["name"] in n["message"] for n in body["notices"]), body["notices"]
        else:
            assert not body["notices"]
    assert fixed, "no flight option pushed arrival past the added visit; pick a request where one does"


def test_checkin_warning_matches_the_arrival_time(client):
    seen_early = False
    trip = new_package(client)
    for t in [trip] + [change_arrival(client, trip, o["flight_id"]).json() for o in flight_options(client, trip)]:
        hotel, reach = item(t, "hotel-1"), item(t, "transfer-arrival")["end"]
        early = reach[:10] == hotel["start"] and reach[11:16] < hotel["details"]["check_in_from"]
        assert bool(hotel["warnings"]) == early, (reach, hotel["details"]["check_in_from"], hotel["warnings"])
        seen_early |= early
    assert seen_early, "no arrival before check-in in this data; pick a request where one exists"
