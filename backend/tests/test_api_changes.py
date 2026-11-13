"""Phase 2 API tests: changing a package (M6). Contract: docs/API.md, "Phase 2".

These fail until Phase 2 is built. Run Phase 1 alone with:
    pytest --ignore=tests/test_api_changes.py
"""
from datetime import date, datetime, timedelta

import pytest

from tests.check_trip import DAYS, check, load_catalog, mins

CAT = load_catalog()
MENON = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}


@pytest.fixture
def pkg(client):
    r = client.post("/api/packages/search", json=MENON)
    assert r.status_code == 201, r.text
    return r.json()


def items(trip, type_):
    return [i for i in trip["items"] if i["type"] == type_]


def change(client, trip, body):
    r = client.patch(f"/api/packages/{trip['trip_id']}", json=body)
    new = r.json()
    if r.status_code == 200:
        assert check(new, CAT, first_package=False) == []
        assert new["total_inr"] == sum(i["price_inr"] for i in new["items"])
    return r.status_code, new


def assert_refused(client, trip, status, body):
    assert status == 422 and body["code"] == "CHANGE_REFUSED" and body["error"].strip(), body
    assert body["reasons"] and body["error"] == body["reasons"][0]
    assert isinstance(body["blockers"], list)
    assert client.get(f"/api/packages/{trip['trip_id']}").json() == trip  # unchanged


def stay(trip, idx=0):
    h = sorted(items(trip, "hotel"), key=lambda i: i["start"])[idx]
    return h, CAT["hotels"][h["catalog_id"]]["city"], date.fromisoformat(h["start"]), date.fromisoformat(h["end"])


def rooms_ok(room, n_rooms, ci, co):
    return all(CAT["avail"].get((room["room_id"], (ci + timedelta(d)).isoformat()), 0) >= n_rooms
               for d in range((co - ci).days))


def flight_items(trip):
    home = trip["traveler"]["home_airport"]
    fl = items(trip, "flight")
    return (next(i for i in fl if CAT["flights"][i["catalog_id"]]["from"] == home),
            next(i for i in fl if CAT["flights"][i["catalog_id"]]["to"] == home))


# ---------- hotels ----------

def test_change_hotel_to_other_hotel_in_city(client, pkg):
    h, city, ci, co = stay(pkg)
    room = next(r for r in CAT["rooms"].values() if CAT["hotels"][r["hotel_id"]]["city"] == city
                and r["hotel_id"] != h["catalog_id"] and r["max_adults"] >= 2 and r["max_children"] >= 1
                and rooms_ok(r, 1, ci, co))
    status, new = change(client, pkg, {"action": "change_hotel", "city": city, "hotel_id": room["hotel_id"],
                                       "room_id": room["room_id"]})
    assert status == 200
    assert any(i["catalog_id"] == room["hotel_id"] and i["room_id"] == room["room_id"] for i in items(new, "hotel"))


def test_change_hotel_to_sold_out_room_refused(client, pkg):
    _, city, ci, co = stay(pkg)
    room = next(r for r in CAT["rooms"].values()
                if CAT["hotels"][r["hotel_id"]]["city"] == city and not rooms_ok(r, 1, ci, co))
    status, body = change(client, pkg, {"action": "change_hotel", "city": city, "hotel_id": room["hotel_id"],
                                        "room_id": room["room_id"]})
    assert_refused(client, pkg, status, body)
    assert body["blockers"][0]["code"] == "HOTEL_SOLD_OUT" and body["blockers"][0]["part"] == "hotel"


def test_change_hotel_to_room_travelers_do_not_fit_refused(client, pkg):
    _, city, _, _ = stay(pkg)
    # SINGLE: 3 travelers need 3 rooms, but each room needs an adult and there are 2
    room = next(r for r in CAT["rooms"].values()
                if CAT["hotels"][r["hotel_id"]]["city"] == city and r["room_type"] == "SINGLE")
    status, body = change(client, pkg, {"action": "change_hotel", "city": city, "hotel_id": room["hotel_id"],
                                        "room_id": room["room_id"]})
    assert_refused(client, pkg, status, body)


def test_hotel_options_show_price_difference(client, pkg):
    h, city, _, _ = stay(pkg)
    r = client.get(f"/api/packages/{pkg['trip_id']}/options/hotels", params={"city": city})
    assert r.status_code == 200
    opts = r.json()["options"]
    assert opts
    for o in opts:
        assert CAT["hotels"][o["hotel_id"]]["city"] == city
        assert o["price_diff_inr"] == o["price_inr"] - h["price_inr"]


# ---------- flights ----------

def test_change_arrival_flight_to_other_valid_flight(client, pkg):
    out, _ = flight_items(pkg)
    cur = CAT["flights"][out["catalog_id"]]
    first_city = stay(pkg)[1]
    alt = [f for f in CAT["flights"].values() if f["flight_id"] != cur["flight_id"] and f["from"] == cur["from"]
           and f["arrival_local"][:10] == pkg["start_date"] and f["seats_left"] >= 3
           and first_city in (CAT["airports"][f["to"]].get("serves_cities") or [])]
    if not alt:
        pytest.skip("catalog has no other arrival flight for this package")
    status, new = change(client, pkg, {"action": "change_flight", "item_id": out["item_id"],
                                       "flight_id": alt[0]["flight_id"]})
    # 422 only if the new landing time breaks the airport transfer and the app cannot repair it
    assert status in (200, 422), new
    if status == 200:
        assert any(i["catalog_id"] == alt[0]["flight_id"] for i in items(new, "flight"))


def test_change_arrival_flight_to_wrong_date_refused(client, pkg):
    out, _ = flight_items(pkg)
    cur = CAT["flights"][out["catalog_id"]]
    wrong = next(f for f in CAT["flights"].values() if f["from"] == cur["from"] and f["to"] == cur["to"]
                 and f["arrival_local"][:10] != pkg["start_date"])
    status, body = change(client, pkg, {"action": "change_flight", "item_id": out["item_id"],
                                        "flight_id": wrong["flight_id"]})
    assert_refused(client, pkg, status, body)


# ---------- attractions ----------

def test_remove_attraction(client, pkg):
    att = items(pkg, "attraction")[0]
    status, new = change(client, pkg, {"action": "remove_attraction", "item_id": att["item_id"]})
    assert status == 200
    assert att["item_id"] not in [i["item_id"] for i in new["items"]]
    assert new["total_inr"] == pkg["total_inr"] - att["price_inr"]


def test_add_duplicate_attraction_refused(client, pkg):
    att = items(pkg, "attraction")[0]
    status, body = change(client, pkg, {"action": "add_attraction", "attraction_id": att["catalog_id"],
                                        "start": att["start"][:16]})
    assert_refused(client, pkg, status, body)


def test_add_attraction_on_closed_date_refused(client, pkg):
    hotel_days = [(CAT["hotels"][h["catalog_id"]]["city"], date.fromisoformat(h["start"]) + timedelta(d))
                  for h in items(pkg, "hotel")
                  for d in range((date.fromisoformat(h["end"]) - date.fromisoformat(h["start"])).days)]
    closed = [(a, day) for city, day in hotel_days for a in CAT["attractions"].values() if a["city"] == city
              and (day.isoformat() in a.get("closed_dates", []) or DAYS[day.weekday()] not in a["open_days"])]
    if not closed:
        pytest.skip("no attraction is closed on any day of this package")
    a, day = closed[0]
    status, body = change(client, pkg, {"action": "add_attraction", "attraction_id": a["attraction_id"],
                                        "start": f"{day}T{a['open_from']}"})
    assert_refused(client, pkg, status, body)


def test_add_attraction_in_other_city_refused(client, pkg):
    _, city, ci, _ = stay(pkg)
    country_cities = {c["name"] for c in CAT["dest"]["countries"][0]["cities"]}
    other = next(a for a in CAT["attractions"].values() if a["city"] != city and a["city"] in country_cities)
    day = ci + timedelta(1)
    status, body = change(client, pkg, {"action": "add_attraction", "attraction_id": other["attraction_id"],
                                        "start": f"{day}T{other['open_from']}"})
    assert_refused(client, pkg, status, body)


def test_add_attraction_on_last_day_refused(client, pkg):
    a = next(a for a in CAT["attractions"].values() if a["city"] == stay(pkg, -1)[1])
    status, body = change(client, pkg, {"action": "add_attraction", "attraction_id": a["attraction_id"],
                                        "start": f"{pkg['end_date']}T{a['open_from']}"})
    assert_refused(client, pkg, status, body)


def test_add_overlapping_attraction_refused(client, pkg):
    att = items(pkg, "attraction")[0]
    city = CAT["attractions"][att["catalog_id"]]["city"]
    used = {i["catalog_id"] for i in items(pkg, "attraction")}
    s = datetime.fromisoformat(att["start"])
    sm = s.hour * 60 + s.minute
    # open that day and at that time, so the overlap is the only reason to refuse
    other = next(a for a in CAT["attractions"].values() if a["city"] == city and a["attraction_id"] not in used
                 and DAYS[s.weekday()] in a["open_days"] and s.date().isoformat() not in a.get("closed_dates", [])
                 and mins(a["open_from"]) <= sm and sm + a["visit_minutes"] <= mins(a["open_until"]))
    status, body = change(client, pkg, {"action": "add_attraction", "attraction_id": other["attraction_id"],
                                        "start": att["start"][:16]})
    assert_refused(client, pkg, status, body)


# ---------- booked packages ----------

def test_booked_package_cannot_change(client, pkg):
    client.post(f"/api/packages/{pkg['trip_id']}/book")
    att = items(pkg, "attraction")[0]
    r = client.patch(f"/api/packages/{pkg['trip_id']}", json={"action": "remove_attraction", "item_id": att["item_id"]})
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_BOOKED"
