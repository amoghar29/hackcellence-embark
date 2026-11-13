"""Change options list only changes that work, and each carries its preview: the package that choosing it gives.

The preview is what the change call returns for that option, so the client can show what it changes, removes and
costs before the traveler picks it.
"""
import uuid

from tests.test_api import package_body, search


def options(client, pkg, kind, **q):
    r = client.post(f"/api/packages/options/{kind}", json=dict(package_body(pkg), **q))
    assert r.status_code == 200, r.text
    return r.json()["options"]


def change(client, pkg, body):
    return client.post("/api/packages/change", json=dict(package_body(pkg), change=body))


def assert_previews_match(client, pkg, opts, body_for):
    for o in opts:
        r = change(client, pkg, body_for(o))
        assert r.status_code == 200, f"listed option must work: {o} -> {r.text}"
        new = r.json()
        assert o["preview"]["total_inr"] == new["total_inr"]
        assert o["preview"]["notices"] == new["notices"]
        assert [i["item_id"] for i in o["preview"]["items"]] == [i["item_id"] for i in new["items"]]


def test_hotel_options_work_and_carry_preview(client):
    pkg = search(client)
    for c in pkg["cities"]:
        opts = options(client, pkg, "hotels", city=c["city"])
        assert_previews_match(client, pkg, opts, lambda o: {"action": "change_hotel", "city": c["city"],
                                                             "hotel_id": o["hotel_id"], "room_id": o["room_id"]})


def test_flight_options_work_and_carry_preview(client):
    pkg = search(client)
    for direction, item_id in (("ARRIVAL", "flight-arrival"), ("RETURN", "flight-return")):
        opts = options(client, pkg, "flights", direction=direction)
        assert_previews_match(client, pkg, opts, lambda o: {"action": "change_flight", "item_id": item_id,
                                                             "flight_id": o["flight_id"]})


def test_attraction_options_carry_preview(client):
    pkg = search(client)
    opts = options(client, pkg, "attractions", date=pkg["days"][2]["date"])
    assert opts
    assert_previews_match(client, pkg, opts, lambda o: {"action": "add_attraction",
                                                         "attraction_id": o["attraction_id"], "start": o["start"]})


def test_city_plan_options_carry_preview(client):
    pkg = search(client)
    opts = [o for o in options(client, pkg, "city-plans") if not o["is_current"]]
    assert opts
    assert_previews_match(client, pkg, opts[:5], lambda o: {"action": "change_city_plan", "plan": o["plan"]})


def test_options_skip_changes_the_rest_of_the_package_refuses(client):
    """Booking the package takes its seats and rooms; the same (unbooked) package now fails elsewhere, so a stay
    whose own rooms are free must still not be offered when choosing it would be refused."""
    pkg = search(client)
    r = client.post("/api/bookings", json=package_body(pkg), headers={"Idempotency-Key": uuid.uuid4().hex})
    assert r.status_code in (200, 201), r.text
    for c in pkg["cities"]:
        opts = options(client, pkg, "hotels", city=c["city"])
        assert_previews_match(client, pkg, opts, lambda o: {"action": "change_hotel", "city": c["city"],
                                                             "hotel_id": o["hotel_id"], "room_id": o["room_id"]})


def test_empty_attraction_day_says_why(client):
    """A day with no option says why: a travel day that already has its one visit says so, not "nothing is open"."""
    from datetime import date, timedelta
    pkg = search(client)
    start, seen_travel_day = date.fromisoformat(pkg["start_date"]), False
    change_days = {start}
    for c in pkg["cities"][:-1]:
        start += timedelta(c["nights"])
        change_days.add(start)
    for d in pkg["days"]:
        r = client.post("/api/packages/options/attractions", json=dict(package_body(pkg), date=d["date"]))
        body = r.json()
        assert r.status_code == 200 and "reason" in body, body
        if body["options"]:
            assert body["reason"] is None
            continue
        assert body["reason"].strip()
        visits = [i for i in pkg["items"] if i["type"] == "attraction" and i["start"][:10] == d["date"]]
        if date.fromisoformat(d["date"]) in change_days and visits:
            seen_travel_day = True
            assert "travel day" in body["reason"] and visits[0]["name"] in body["reason"], body["reason"]
    assert seen_travel_day, "no travel day with its visit in this package; pick a request where one exists"
