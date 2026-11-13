"""Phase 1 API tests. Contract: docs/API.md.

Every package the API returns must pass check_trip.py, which reads the JSON catalog
directly (not the app's DB), so it stays an independent judge of the app.
"""
import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.check_trip import check, load_catalog

CAT = load_catalog()

REQUIRED_TRIP = {"trip_id", "traveler", "start_date", "end_date", "country", "budget_inr", "total_inr", "items"}
REQUIRED_ITEM = {"item_id", "type", "name", "city", "status", "catalog_id", "start", "end",
                 "room_id", "quantity", "price_inr", "booking", "sources"}
UI_ONLY_TRIP = {"nights", "cities", "remaining_inr", "days"}
DETAILS = {
    "flight": {"direction", "airline", "flight_number", "from_airport", "to_airport", "stops",
               "duration_minutes", "price_per_seat_inr"},
    "hotel": {"area", "stars", "rating", "room_type", "room_name", "rooms", "nights",
              "price_per_night_inr", "check_in_from", "check_out_until", "image"},
    "transfer": {"kind", "transfer_type", "from_point", "to_point", "duration_minutes", "pricing"},
    "attraction": {"category", "visit_minutes", "open_from", "open_until", "child_friendly", "image"},
}
DAY_TYPES = {"TRAVEL", "ARRIVAL", "FULL", "CITY_CHANGE", "RETURN", "HOME"}
EVENT_KINDS = {"FLIGHT_DEPARTURE", "FLIGHT_ARRIVAL", "TRANSFER", "CHECK_IN", "CHECK_OUT", "ATTRACTION"}


def request(departure_city="BLR", country="Japan", start="2027-04-10", nights=6, adults=2,
            child_ages=(6,), budget=350000):
    return {"departure_city": departure_city, "country": country, "start_date": start, "nights": nights,
            "adults": adults, "child_ages": list(child_ages), "budget_inr": budget}


MENON = request()


def search(client, req=MENON):
    r = client.post("/api/packages/search", json=req)
    assert r.status_code == 201, r.text
    return r.json()


def of_type(pkg, type_):
    return [i for i in pkg["items"] if i["type"] == type_]


def assert_not_found(r):
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "NOT_FOUND" and "not found" in body["error"].lower()


# ---------- form options ----------

def test_options_include_rules(client):
    body = client.get("/api/options").json()
    assert body["rules"] == {"min_nights": 3, "max_nights": 10, "min_nights_per_city": 2,
                             "first_night": "2027-04-01", "last_departure": "2027-04-20"}


# ---------- 1. search: a correct package for many requests (M2, M3, M5) ----------

BUILD_CASES = {
    "menon": MENON,
    "uae_from_delhi": request("DEL", "United Arab Emirates", "2027-04-05", 4, 2, (), 300000),
    "min_nights_window_start": request("MAA", "Japan", "2027-04-01", 3, 1, (), 300000),
    "max_nights_window_end": request("BLR", "Japan", "2027-04-10", 10, 2, (), 1000000),
    "big_family_many_rooms_vehicles": request("BLR", "United Arab Emirates", "2027-04-12", 6, 4, (0, 12), 1000000),
    "child_age_17": request("DEL", "Japan", "2027-04-03", 5, 1, (17,), 500000),
}


@pytest.mark.parametrize("req", BUILD_CASES.values(), ids=BUILD_CASES.keys())
def test_search_returns_correct_package(client, req):
    pkg = search(client, req)
    assert check(pkg, CAT) == []
    t = pkg["traveler"]
    assert (pkg["start_date"], pkg["country"], t["home_airport"], t["adults"], t["child_ages"], t["children"]) == (
        req["start_date"], req["country"], req["departure_city"], req["adults"], req["child_ages"],
        len(req["child_ages"]))
    assert pkg["nights"] == req["nights"]
    assert (date.fromisoformat(pkg["end_date"]) - date.fromisoformat(pkg["start_date"])).days == req["nights"]
    assert pkg["budget_inr"] == req["budget_inr"]
    assert pkg["total_inr"] <= req["budget_inr"]
    assert pkg["remaining_inr"] == req["budget_inr"] - pkg["total_inr"]
    assert pkg["status"] == "PLANNED" and pkg["reference"] is None


def test_package_shape(client):
    pkg = search(client)
    assert REQUIRED_TRIP <= pkg.keys()
    ids = [i["item_id"] for i in pkg["items"]]
    assert len(ids) == len(set(ids))
    assert pkg["total_inr"] == sum(i["price_inr"] for i in pkg["items"])
    assert [i["start"] for i in pkg["items"]] == sorted(i["start"] for i in pkg["items"])
    for it in pkg["items"]:
        assert REQUIRED_ITEM <= it.keys()
        assert it["status"] == "PLANNED" and it["booking"] is None and it["sources"] == []
        assert (it["room_id"] is not None) == (it["type"] == "hotel")
        assert DETAILS[it["type"]] <= it["details"].keys()
    assert len(of_type(pkg, "flight")) == 2


def test_city_plan_matches_hotels(client):
    pkg = search(client)
    hotels = of_type(pkg, "hotel")
    assert [(c["city"], c["check_in"], c["check_out"]) for c in pkg["cities"]] == [
        (h["city"], h["start"], h["end"]) for h in hotels]
    assert sum(c["nights"] for c in pkg["cities"]) == pkg["nights"]
    assert all(c["nights"] >= 2 for c in pkg["cities"])


def test_request_values_are_normalized(client):
    pkg = search(client, dict(MENON, departure_city=" bengaluru ", country="japan", budget_inr="3,50,000"))
    assert pkg["traveler"]["home_airport"] == "BLR"
    assert pkg["country"] == "Japan"
    assert pkg["budget_inr"] == 350000


def test_children_are_optional(client):
    req = {k: v for k, v in MENON.items() if k != "child_ages"}
    pkg = search(client, req)
    assert pkg["traveler"]["children"] == 0 and pkg["traveler"]["child_ages"] == []
    assert check(pkg, CAT) == []


# ---------- 1. search: invalid input (M1) ----------

INVALID = {
    "nights_below_3": ("nights", dict(MENON, nights=2)),
    "nights_above_10": ("nights", dict(MENON, nights=11)),
    "no_adults": ("adults", dict(MENON, adults=0)),
    "child_age_18": ("child_ages", dict(MENON, child_ages=[18])),
    "child_age_negative": ("child_ages", dict(MENON, child_ages=[-1])),
    "unknown_country": ("country", dict(MENON, country="France")),
    "unknown_departure": ("departure_city", dict(MENON, departure_city="XYZ")),
    "destination_airport_as_departure": ("departure_city", dict(MENON, departure_city="NRT")),
    "impossible_date": ("start_date", dict(MENON, start_date="2027-02-30")),
    "bad_date_text": ("start_date", dict(MENON, start_date="10/04/2027")),
    "before_1_april": ("start_date", dict(MENON, start_date="2027-03-29")),
    "return_after_20_april": ("start_date", dict(MENON, start_date="2027-04-18", nights=5)),
    "zero_budget": ("budget_inr", dict(MENON, budget_inr=0)),
    "negative_budget": ("budget_inr", dict(MENON, budget_inr=-1)),
    "missing_nights": ("nights", {k: v for k, v in MENON.items() if k != "nights"}),
    "missing_country": ("country", {k: v for k, v in MENON.items() if k != "country"}),
}


@pytest.mark.parametrize("field,req", INVALID.values(), ids=INVALID.keys())
def test_invalid_input_names_the_field(client, field, req):
    r = client.post("/api/packages/search", json=req)
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["code"] == "INVALID_REQUEST" and body["error"].strip() and body["field"] == field


@pytest.mark.parametrize("body", [["BLR", "Japan"], "BLR", None])
def test_body_not_an_object(client, body):
    r = client.post("/api/packages/search", json=body)
    assert r.status_code == 400 and r.json()["code"] == "INVALID_REQUEST"


# ---------- 1. search: no possible package (M2) ----------

NO_PACKAGE = {
    "more_travelers_than_any_flight_has_seats": dict(MENON, adults=8, child_ages=[5, 7]),  # max seats_left is 9
    "no_flight_lands_that_day": request("BOM", "Japan", "2027-04-03", 5, 2, (), 1000000),
}


@pytest.mark.parametrize("req", NO_PACKAGE.values(), ids=NO_PACKAGE.keys())
def test_no_possible_package_says_why(client, req):
    r = client.post("/api/packages/search", json=req)
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "NO_PACKAGE" and body["error"].strip()
    assert body["reasons"] and all(isinstance(x, str) and x.strip() for x in body["reasons"])


# ---------- 1. search: budget too small (M8) ----------

def test_budget_too_small_shows_cheapest_and_suggestion(client):
    r = client.post("/api/packages/search", json=dict(MENON, budget_inr=10000))
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "OVER_BUDGET" and body["error"].strip()
    assert body["budget_inr"] == 10000
    assert body["cheapest_total_inr"] > 10000
    assert body["over_by_inr"] == body["cheapest_total_inr"] - 10000
    assert body["suggestion"].strip()


def test_cheapest_total_is_really_buildable(client):
    cheapest = client.post("/api/packages/search", json=dict(MENON, budget_inr=10000)).json()["cheapest_total_inr"]
    pkg = search(client, dict(MENON, budget_inr=cheapest))
    assert pkg["total_inr"] <= cheapest
    assert check(pkg, CAT) == []
    r = client.post("/api/packages/search", json=dict(MENON, budget_inr=cheapest - 1))
    assert r.status_code == 422 and r.json()["code"] == "OVER_BUDGET"


# ---------- 1. saved package, export ----------

def test_package_is_saved(client):
    pkg = search(client)
    r = client.get(f"/api/packages/{pkg['trip_id']}")
    assert r.status_code == 200 and r.json() == pkg


def test_package_survives_backend_restart(client):
    pkg = search(client)
    from app.main import create_app

    with TestClient(create_app()) as fresh:
        assert fresh.get(f"/api/packages/{pkg['trip_id']}").json() == pkg


def test_unknown_package_not_found(client):
    assert_not_found(client.get("/api/packages/does-not-exist"))


def test_export_is_the_shared_trip_format(client):
    pkg = search(client)
    r = client.get(f"/api/packages/{pkg['trip_id']}/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert f"trip-{pkg['trip_id']}.json" in r.headers["content-disposition"]
    trip = r.json()
    assert REQUIRED_TRIP <= trip.keys()
    assert not UI_ONLY_TRIP & trip.keys()
    assert trip["country"] == "Japan"
    assert check(trip, CAT) == []
    assert trip["total_inr"] == sum(i["price_inr"] for i in trip["items"])
    for it in trip["items"]:
        assert REQUIRED_ITEM <= it.keys() and "details" not in it
        assert it["sources"] == []
        assert (it["room_id"] is not None) == (it["type"] == "hotel")
    assert [i["item_id"] for i in trip["items"]] == [i["item_id"] for i in pkg["items"]]


def test_export_unknown_package_not_found(client):
    assert_not_found(client.get("/api/packages/does-not-exist/export"))


# ---------- day-by-day plan (M4) ----------

def test_days_cover_the_trip_in_time_order(client):
    pkg = search(client)
    days = pkg["days"]
    dates = [date.fromisoformat(d["date"]) for d in days]
    assert dates == [dates[0] + timedelta(n) for n in range(len(dates))]  # in order, no gaps
    start, end = date.fromisoformat(pkg["start_date"]), date.fromisoformat(pkg["end_date"])
    assert dates[0] <= start and dates[-1] >= end
    for d, day in zip(dates, days):
        assert day["day_type"] in DAY_TYPES
        if d < start:
            assert day["day_type"] == "TRAVEL"
        elif d == start:
            assert day["day_type"] == "ARRIVAL"
        elif d == end:
            assert day["day_type"] == "RETURN"
        elif d > end:
            assert day["day_type"] == "HOME"
        else:
            assert day["day_type"] in {"FULL", "CITY_CHANGE"}
        times = [e["time"] for e in day["events"]]
        assert times == sorted(times)
        assert all(re.fullmatch(r"\d\d:\d\d", t) for t in times)
        assert all(e["kind"] in EVENT_KINDS and e["title"].strip() and e["timezone"] for e in day["events"])
    assert sum(d["day_type"] == "CITY_CHANGE" for d in days) == len(of_type(pkg, "hotel")) - 1


def test_every_item_is_on_the_day_plan(client):
    pkg = search(client)
    on_plan = {e["item_id"] for d in pkg["days"] for e in d["events"]}
    assert on_plan == {i["item_id"] for i in pkg["items"]}
    events = [(d["date"], e["kind"], e["item_id"]) for d in pkg["days"] for e in d["events"]]
    for h in of_type(pkg, "hotel"):
        assert (h["start"], "CHECK_IN", h["item_id"]) in events
        assert (h["end"], "CHECK_OUT", h["item_id"]) in events
    for a in of_type(pkg, "attraction"):
        assert (a["start"][:10], "ATTRACTION", a["item_id"]) in events


def test_day_city_is_that_nights_hotel(client):
    pkg = search(client)
    night_city = {}
    for h in of_type(pkg, "hotel"):
        d = date.fromisoformat(h["start"])
        while d < date.fromisoformat(h["end"]):
            night_city[d.isoformat()] = h["city"]
            d += timedelta(1)
    for day in pkg["days"]:
        if day["day_type"] in {"TRAVEL", "HOME"}:
            assert day["city"] is None
        elif day["day_type"] == "RETURN":
            assert day["city"] == of_type(pkg, "hotel")[-1]["city"]
        else:
            assert day["city"] == night_city[day["date"]]


# ---------- 3. parts of a package ----------

@pytest.mark.parametrize("part,type_", [("flights", "flight"), ("hotels", "hotel"),
                                        ("transfers", "transfer"), ("attractions", "attraction")])
def test_package_parts(client, part, type_):
    pkg = search(client)
    r = client.get(f"/api/packages/{pkg['trip_id']}/{part}")
    assert r.status_code == 200
    body = r.json()
    assert body["trip_id"] == pkg["trip_id"]
    assert body["items"] == of_type(pkg, type_)


def test_package_days_part(client):
    pkg = search(client)
    r = client.get(f"/api/packages/{pkg['trip_id']}/days")
    assert r.status_code == 200 and r.json() == {"trip_id": pkg["trip_id"], "days": pkg["days"]}


@pytest.mark.parametrize("part", ["flights", "hotels", "transfers", "attractions", "days"])
def test_parts_of_unknown_package_not_found(client, part):
    assert_not_found(client.get(f"/api/packages/does-not-exist/{part}"))


def test_item_details_match_catalog(client):
    pkg = search(client)
    for it in of_type(pkg, "hotel"):
        h, room = CAT["hotels"][it["catalog_id"]], CAT["rooms"][it["room_id"]]
        d = it["details"]
        assert (d["area"], d["stars"], d["room_type"], d["rooms"], d["price_per_night_inr"]) == (
            h["area"], h["stars"], room["room_type"], it["quantity"], room["price_per_night"]["amount"])
        assert d["image"] == "/" + h["image"]
    home = pkg["traveler"]["home_airport"]
    for it in of_type(pkg, "flight"):
        f = CAT["flights"][it["catalog_id"]]
        assert it["details"]["direction"] == ("ARRIVAL" if f["from"] == home else "RETURN")
        assert it["details"]["price_per_seat_inr"] == f["price_per_seat"]["amount"]
    kinds = sorted(t["details"]["kind"] for t in of_type(pkg, "transfer"))
    assert kinds.count("AIRPORT_ARRIVAL") == 1 and kinds.count("AIRPORT_RETURN") == 1
    assert kinds.count("INTERCITY") == len(of_type(pkg, "hotel")) - 1


# ---------- 3. details from the catalog ----------

def test_hotel_details_with_rooms(client):
    r = client.get("/api/hotels/HTL-TYO-004")
    assert r.status_code == 200
    h = r.json()
    assert (h["hotel_id"], h["name"], h["city"], h["area"], h["stars"], h["rating"]) == (
        "HTL-TYO-004", "Ueno Garden Inn", "Tokyo", "Ueno", 3, 7.9)
    assert (h["check_in_from"], h["check_out_until"], h["family_friendly"]) == ("15:00", "11:00", True)
    assert h["image"] == "/images/hotels/HOTEL-BUSINESS-1.jpg"
    assert sorted((x["room_id"], x["room_type"], x["max_adults"], x["max_children"], x["price_per_night_inr"],
                   x["refundable"]) for x in h["rooms"]) == [
        ("RM-TYO-004-A", "TWIN", 2, 0, 7000, True),
        ("RM-TYO-004-B", "FAMILY", 2, 2, 9464, False),
    ]


def test_flight_details(client):
    f = client.get("/api/flights/FL-711").json()
    assert (f["flight_id"], f["from_airport"], f["to_airport"], f["departure_local"], f["arrival_local"]) == (
        "FL-711", "BLR", "KIX", "2027-04-03T06:30", "2027-04-03T20:30")
    assert (f["stops"], f["duration_minutes"], f["price_per_seat_inr"], f["seats_left"]) == (1, 630, 25200, 9)
    assert f["to_airport_name"] == "Kansai International Airport"


def test_transfer_details(client):
    t = client.get("/api/transfers/TR-KIX-KYO-TAXI").json()
    assert (t["type"], t["airport"], t["city"], t["area"], t["max_passengers"]) == ("AIRPORT_TAXI", "KIX", "Kyoto", None, 4)
    assert (t["service_from"], t["service_until"], t["pricing"], t["price_inr"], t["child_price_inr"]) == (
        "06:00", "23:00", "PER_VEHICLE", 16800, None)
    assert (t["from_city"], t["to_city"], t["frequency_minutes"]) == (None, None, None)
    train = client.get("/api/transfers/TR-TYO-KYO-01").json()
    assert (train["from_city"], train["to_city"], train["frequency_minutes"], train["child_price_inr"]) == (
        "Tokyo", "Kyoto", 30, 3968)


def test_attraction_details(client):
    a = client.get("/api/attractions/ATT-TYO-002").json()
    assert (a["name"], a["city"], a["category"], a["visit_minutes"]) == (
        CAT["attractions"]["ATT-TYO-002"]["name"], "Tokyo", "THEME_PARK", 480)
    assert a["closed_dates"] == ["2027-04-12"]
    assert a["image"] == "/images/attractions/ATT-TYO-002.jpg"
    assert client.get("/api/attractions/ATT-KYO-001").json()["closed_dates"] == []
    assert client.get("/api/attractions/ATT-TYO-005").json()["child_price_inr"] == 0  # children free
    assert client.get("/api/attractions/ATT-KYO-005").json()["child_price_inr"] is None  # no child price


@pytest.mark.parametrize("path", ["/api/hotels/HTL-XXX", "/api/flights/FL-0", "/api/transfers/TR-NONE",
                                  "/api/attractions/ATT-NONE"])
def test_unknown_catalog_id_not_found(client, path):
    assert_not_found(client.get(path))


# ---------- media ----------

def test_images_are_served(client):
    r = client.get("/images/attractions/ATT-KYO-001.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_credits(client):
    r = client.get("/api/credits")
    assert r.status_code == 200 and "ATT-KYO-001" in r.json()["markdown"]


# ---------- 2. book and reservation (M7) ----------

def test_book_gives_10_digit_reference_and_booked_package(client):
    pkg = search(client)
    r = client.post(f"/api/packages/{pkg['trip_id']}/book")
    assert r.status_code == 200
    body = r.json()
    ref = body["reference"]
    assert re.fullmatch(r"[1-9]\d{9}", ref)
    booked = body["package"]
    assert booked["trip_id"] == pkg["trip_id"]
    assert booked["status"] == "BOOKED" and booked["reference"] == ref
    assert all(i["status"] == "BOOKED" and i["booking"] == {"reference": ref} for i in booked["items"])
    assert booked["total_inr"] == pkg["total_inr"]
    assert check(booked, CAT) == []


def test_reservation_opens_the_booked_package(client):
    pkg = search(client)
    booked = client.post(f"/api/packages/{pkg['trip_id']}/book").json()
    r = client.get(f"/api/reservations/{booked['reference']}")
    assert r.status_code == 200 and r.json() == booked["package"]
    assert client.get(f"/api/packages/{pkg['trip_id']}").json() == booked["package"]


def test_export_after_booking_is_booked(client):
    pkg = search(client)
    ref = client.post(f"/api/packages/{pkg['trip_id']}/book").json()["reference"]
    trip = client.get(f"/api/packages/{pkg['trip_id']}/export").json()
    assert trip["status"] == "BOOKED"
    assert all(i["status"] == "BOOKED" and i["booking"] == {"reference": ref} for i in trip["items"])
    assert check(trip, CAT) == []


def test_booking_twice_keeps_the_reference(client):
    pkg = search(client)
    first = client.post(f"/api/packages/{pkg['trip_id']}/book").json()["reference"]
    second = client.post(f"/api/packages/{pkg['trip_id']}/book").json()["reference"]
    assert first == second


def test_references_are_unique(client):
    refs = {client.post(f"/api/packages/{search(client)['trip_id']}/book").json()["reference"] for _ in range(3)}
    assert len(refs) == 3


def test_reservation_survives_backend_restart(client):
    pkg = search(client)
    booked = client.post(f"/api/packages/{pkg['trip_id']}/book").json()
    from app.main import create_app

    with TestClient(create_app()) as fresh:
        r = fresh.get(f"/api/reservations/{booked['reference']}")
        assert r.status_code == 200 and r.json() == booked["package"]


def test_book_unknown_package_not_found(client):
    assert_not_found(client.post("/api/packages/does-not-exist/book"))


@pytest.mark.parametrize("ref", ["0000000000", "9999999999", "123", "abcdefghij"])
def test_wrong_reservation_number_not_found(client, ref):
    assert_not_found(client.get(f"/api/reservations/{ref}"))
