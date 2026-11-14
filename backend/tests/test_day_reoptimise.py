"""A change that touches a day (removing a visit, another hotel, another flight) plans that day again the
builder's way: every visit starts as early as the rules allow (VISIT_FROM, opening time, arrival + check-in +
travel, the previous visit + overrun + STOP_BUFFER + travel), rounded up to 5 minutes. A day that cannot be
planned again keeps its times and its warnings. An added visit keeps the time the traveler picked."""
import math
from datetime import datetime, timedelta

from app.services.builder import VISIT_FROM
from app.services.travel import CHECKIN_BUFFER, OVERRUN, STOP_BUFFER
from tests.check_trip import check, load_catalog
from tests.test_api import package_body

CAT = load_catalog()
MENON = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}
# Japan's other arrival flights all land too late to keep the visit; here an earlier one moves it up
UAE = dict(MENON, country="United Arab Emirates", start_date="2027-04-03")


def search(client, request=MENON):
    r = client.post("/api/packages/search", json=request)
    assert r.status_code == 201, r.text
    return r.json()


def change(client, trip, body):
    r = client.post("/api/packages/change", json=dict(package_body(trip), change=body))
    assert r.status_code == 200, r.text
    new = r.json()
    assert check({k: v for k, v in new.items() if k != "notices"}, CAT, first_package=False) == []
    return new


def options(client, trip, kind, **extra):
    r = client.post(f"/api/packages/options/{kind}", json=dict(package_body(trip), **extra))
    assert r.status_code == 200, r.text
    return r.json()["options"]


def visits(trip, day):
    return sorted((i for i in trip["items"] if i["type"] == "attraction" and i["start"][:10] == day),
                  key=lambda i: i["start"])


def up5(t):
    return t + timedelta(minutes=-t.minute % 5, seconds=-t.second)


def packed(trip, day):
    """True when every visit of `day` starts at the earliest time the rules allow, in the order planned."""
    reach = [datetime.fromisoformat(i["end"]) for i in trip["items"]
             if i["type"] == "transfer" and i["item_id"] != "transfer-return"]
    free = next((r + timedelta(minutes=CHECKIN_BUFFER) for r in reach if r.date().isoformat() == day), None)
    for v in visits(trip, day):
        d = v["details"]
        earliest = max(datetime.fromisoformat(f"{day}T{VISIT_FROM}"), datetime.fromisoformat(f"{day}T{d['open_from']}"))
        if free:
            earliest = max(earliest, free + timedelta(minutes=d["travel_from"]["minutes"]))
        if datetime.fromisoformat(v["start"]) != up5(earliest):
            return False
        free = datetime.fromisoformat(v["end"]) + timedelta(minutes=math.ceil(d["visit_minutes"] * OVERRUN) + STOP_BUFFER)
    return True


def stay_days(trip, city):
    h = next(i for i in trip["items"] if i["type"] == "hotel" and i["city"] == city)
    start, end = datetime.fromisoformat(h["start"]), datetime.fromisoformat(h["end"])
    return [(start + timedelta(n)).date().isoformat() for n in range((end - start).days)]


def test_removing_a_visit_moves_the_rest_of_its_day_up(client):
    trip = search(client)
    days = sorted({i["start"][:10] for i in trip["items"] if i["type"] == "attraction"})
    tried = 0
    for day in days:
        vs = visits(trip, day)
        if len(vs) < 2:
            continue
        tried += 1
        new = change(client, trip, {"action": "remove_attraction", "item_id": vs[0]["item_id"]})
        left = visits(new, day)
        assert [v["item_id"] for v in left] == [v["item_id"] for v in vs[1:]]
        assert packed(new, day), left
        assert left[0]["start"] < vs[1]["start"], "the next visit should move up into the freed time"
    assert tried, "no day with two visits in this package; pick a request where one exists"


def test_another_hotel_plans_its_days_again(client):
    trip = search(client)
    moved = 0
    for c in trip["cities"]:
        days = [d for d in stay_days(trip, c["city"]) if visits(trip, d)]
        for o in options(client, trip, "hotels", city=c["city"]):
            new = change(client, trip, {"action": "change_hotel", "city": c["city"],
                                        "hotel_id": o["hotel_id"], "room_id": o["room_id"]})
            for day in days:
                vs = visits(new, day)
                assert packed(new, day) or any(v["warnings"] for v in vs), (o["hotel_id"], day, vs)
                old = {v["item_id"]: v["start"] for v in visits(trip, day)}
                moved += any(old.get(v["item_id"], v["start"]) != v["start"] for v in vs)
    assert moved, "no hotel change moved a visit; pick a request where one does"


def test_another_arrival_flight_plans_the_arrival_day_again(client):
    trip = search(client, UAE)
    day = trip["start_date"]
    before = visits(trip, day)
    assert before, "the builder planned no visit on the arrival day; pick a request where it does"
    moved = 0
    for o in options(client, trip, "flights", direction="ARRIVAL"):
        new = change(client, trip, {"action": "change_flight", "item_id": "flight-arrival", "flight_id": o["flight_id"]})
        vs = visits(new, day)
        if vs:  # still reachable: moved to the earliest start after the new arrival, not left where it was
            assert packed(new, day), (o["flight_id"], vs)
            moved += vs[0]["start"] != before[0]["start"]
    assert moved, "no flight option moved the arrival-day visit; pick a request where one does"
