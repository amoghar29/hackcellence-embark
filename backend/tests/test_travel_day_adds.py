"""Adding an experience on an arrival / city-change day: at most one, after reaching the city plus the
check-in buffer and the travel from the hotel, ending CLOSE_BUFFER before closing."""
from datetime import date, datetime, timedelta

import pytest

from app.services.travel import CHECKIN_BUFFER, CLOSE_BUFFER
from tests.check_trip import DAYS, mins
from tests.test_api_changes import CAT, MENON, change, assert_refused, items, pkg  # noqa: F401


def travel_day(trip):
    """(day, city, time the traveler reaches the city) for the arrival day."""
    arr = min(items(trip, "transfer"), key=lambda i: i["start"])  # the first transfer is the airport pickup
    first = min(items(trip, "hotel"), key=lambda i: i["start"])
    return date.fromisoformat(first["start"]), CAT["hotels"][first["catalog_id"]]["city"], datetime.fromisoformat(arr["end"])


def open_attractions(city, day, used):
    return [a for a in CAT["attractions"].values() if a["city"] == city and a["attraction_id"] not in used
            and DAYS[day.weekday()] in a["open_days"] and day.isoformat() not in a.get("closed_dates", [])]


def test_second_visit_on_travel_day_refused(client, pkg):
    day, city, reach = travel_day(pkg)
    used = {i["catalog_id"] for i in items(pkg, "attraction")}
    cands = open_attractions(city, day, used)
    first = next((a for a in cands if True), None)
    # put one visit in late enough to be valid, then try a second
    for a in cands:
        start = max(reach + timedelta(hours=3), datetime.combine(day, datetime.min.time()) + timedelta(minutes=mins(a["open_from"])))
        if start.hour * 60 + start.minute + a["visit_minutes"] <= mins(a["open_until"]) - CLOSE_BUFFER:
            status, one = change(client, pkg, {"action": "add_attraction", "attraction_id": a["attraction_id"],
                                               "start": start.strftime("%Y-%m-%dT%H:%M")})
            if status == 200:
                break
    else:
        pytest.skip("no first visit fits the arrival day")
    used |= {a["attraction_id"]}
    other = next(b for b in open_attractions(city, day, used))
    status, body = change(client, one, {"action": "add_attraction", "attraction_id": other["attraction_id"],
                                        "start": (start + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M")})
    assert_refused(status, body)
    assert "one" in body["error"].lower()


def test_visit_inside_checkin_buffer_refused(client, pkg):
    day, city, reach = travel_day(pkg)
    used = {i["catalog_id"] for i in items(pkg, "attraction")}
    too_early = reach + timedelta(minutes=CHECKIN_BUFFER - 10)
    m = too_early.hour * 60 + too_early.minute
    a = next((a for a in open_attractions(city, day, used)  # open then, so only the buffer can refuse it
              if mins(a["open_from"]) <= m and m + a["visit_minutes"] <= mins(a["open_until"]) - CLOSE_BUFFER), None)
    if not a:
        pytest.skip("nothing is open right after arrival")
    status, body = change(client, pkg, {"action": "add_attraction", "attraction_id": a["attraction_id"],
                                        "start": too_early.strftime("%Y-%m-%dT%H:%M")})
    assert_refused(status, body)


def test_travel_day_visit_ending_inside_close_buffer_refused(client, pkg):
    day, city, reach = travel_day(pkg)
    used = {i["catalog_id"] for i in items(pkg, "attraction")}
    for a in open_attractions(city, day, used):
        start = datetime.combine(day, datetime.min.time()) + timedelta(minutes=mins(a["open_until"]) - a["visit_minutes"])
        if start >= reach + timedelta(hours=3):  # late enough that only the close buffer is wrong
            status, body = change(client, pkg, {"action": "add_attraction", "attraction_id": a["attraction_id"],
                                                "start": start.strftime("%Y-%m-%dT%H:%M")})
            assert_refused(status, body)
            return
    pytest.skip("no attraction on the arrival day is open late enough")
