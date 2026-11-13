"""Every travel rule in section 4, checked against a hand-built valid Menon package.

Fixture items (tests/fixtures/menon_trip.json):
  i1 arrival flight FL-401 BLR->NRT lands 2027-04-10 10:30
  i2 arrival taxi NRT->Ueno 11:30-12:40       i3 Tokyo hotel (Ueno) nights 10,11,12
  i4 attraction arrival day 14:00            i5 full day 04-11
  i6, i7 full day 04-12 (Monday)             i8 train Tokyo->Kyoto 04-13 10:00-12:15
  i9 Kyoto hotel nights 13,14,15             i10 attraction change day 14:00
  i11 full day 04-14                         i12 full day 04-15
  i13 return taxi Kyoto->KIX 04-16 07:30-09:00   i14 return flight FL-411 KIX 12:00
"""
from datetime import datetime, timedelta

import pytest

from app.services.validator import validate

ADULTS, CHILDREN = 2, 1


def codes(trip, cat):
    return {v.split(":")[0] for v in validate(trip, cat)}


def item(trip, item_id):
    return next(i for i in trip["items"] if i["item_id"] == item_id)


def remove(trip, item_id):
    trip["items"] = [i for i in trip["items"] if i["item_id"] != item_id]
    retotal(trip)


def retotal(trip):
    trip["total_inr"] = sum(i["price_inr"] for i in trip["items"])


def fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def set_flight(trip, item_id, flight_id, cat):
    f = cat.flights[flight_id]
    item(trip, item_id).update(
        catalog_id=flight_id,
        start=fmt(f["departure_local"]),
        end=fmt(f["arrival_local"]),
        price_inr=f["price_inr"] * (ADULTS + CHILDREN),
    )
    retotal(trip)


def attraction_fields(attraction_id, start, cat):
    a = cat.attractions[attraction_id]
    s = datetime.fromisoformat(start)
    child = a["child_price_inr"] if a["child_price_inr"] is not None else a["price_inr"]
    return dict(
        catalog_id=attraction_id,
        name=a["name"],
        city=a["city"],
        start=start,
        end=fmt(s + timedelta(minutes=a["visit_minutes"])),
        quantity=ADULTS + CHILDREN,
        price_inr=ADULTS * a["price_inr"] + CHILDREN * child,
    )


def set_attraction(trip, item_id, attraction_id, start, cat):
    item(trip, item_id).update(attraction_fields(attraction_id, start, cat))
    retotal(trip)


def add_attraction(trip, attraction_id, start, cat):
    trip["items"].append(
        dict(
            item_id=f"x{len(trip['items']) + 1}",
            type="attraction",
            status="PLANNED",
            room_id=None,
            booking=None,
            sources=[],
            warnings=[],
            **attraction_fields(attraction_id, start, cat),
        )
    )
    retotal(trip)


def set_transfer_times(trip, item_id, start, cat):
    it = item(trip, item_id)
    t = cat.transfers[it["catalog_id"]]
    s = datetime.fromisoformat(start)
    it.update(start=start, end=fmt(s + timedelta(minutes=t["duration_minutes"])))


def set_hotel(trip, item_id, room_id, check_in, check_out, rooms, cat):
    r = cat.rooms[room_id]
    h = cat.hotels[r["hotel_id"]]
    nights = (datetime.fromisoformat(check_out) - datetime.fromisoformat(check_in)).days
    item(trip, item_id).update(
        catalog_id=h["hotel_id"],
        name=h["name"],
        city=h["city"],
        room_id=room_id,
        start=check_in,
        end=check_out,
        quantity=rooms,
        price_inr=r["price_inr"] * rooms * nights,
    )
    retotal(trip)


# --- the valid package -------------------------------------------------------


def test_hand_built_menon_package_is_valid(menon_trip, cat):
    assert validate(menon_trip, cat) == []


def test_booked_package_is_still_valid(menon_trip, cat):
    for it in menon_trip["items"]:
        it["status"] = "BOOKED"
        it["booking"] = {"reference": "1234567890"}
    assert validate(menon_trip, cat) == []


def test_price_within_one_percent_is_accepted(menon_trip, cat):
    item(menon_trip, "i3")["price_inr"] += 100  # 28392 -> 28492, 0.35%
    retotal(menon_trip)
    assert validate(menon_trip, cat) == []


# --- dates and cities --------------------------------------------------------


def test_trip_shorter_than_three_nights(menon_trip, cat):
    menon_trip["end_date"] = "2027-04-12"
    assert "DATES" in codes(menon_trip, cat)


def test_city_with_one_night(menon_trip, cat):
    set_hotel(menon_trip, "i3", "RM-TYO-004-B", "2027-04-10", "2027-04-11", 1, cat)
    set_hotel(menon_trip, "i9", "RM-KYO-004-B", "2027-04-11", "2027-04-16", 1, cat)
    assert "CITY_NIGHTS" in codes(menon_trip, cat)


def test_city_used_twice(menon_trip, cat):
    set_hotel(menon_trip, "i9", "RM-TYO-003-C", "2027-04-13", "2027-04-16", 1, cat)
    assert "CITY_REPEAT" in codes(menon_trip, cat)


def test_city_outside_the_country(menon_trip, cat):
    room = next(
        r
        for r in cat.rooms.values()
        if cat.hotels[r["hotel_id"]]["city"] == "Dubai" and r["max_children"] >= 1
    )
    set_hotel(menon_trip, "i9", room["room_id"], "2027-04-13", "2027-04-16", 1, cat)
    assert "CITY_COUNTRY" in codes(menon_trip, cat)


# --- flights -----------------------------------------------------------------


def test_arrival_flight_lands_on_wrong_date(menon_trip, cat):
    set_flight(menon_trip, "i1", "FL-402", cat)  # BLR->NRT lands 04-11
    assert "FLIGHT_ARRIVAL" in codes(menon_trip, cat)


def test_arrival_airport_does_not_serve_first_city(menon_trip, cat):
    set_flight(menon_trip, "i1", "FL-740", cat)  # BLR->KIX lands 04-10, KIX does not serve Tokyo
    assert "FLIGHT_ARRIVAL" in codes(menon_trip, cat)


def test_return_flight_on_wrong_date(menon_trip, cat):
    other = next(
        f
        for f in cat.flights.values()
        if f["from_airport"] == "KIX"
        and f["to_airport"] == "BLR"
        and f["departure_local"].date().isoformat() == "2027-04-15"
    )
    set_flight(menon_trip, "i14", other["flight_id"], cat)
    assert "FLIGHT_RETURN" in codes(menon_trip, cat)


def test_missing_return_flight(menon_trip, cat):
    remove(menon_trip, "i14")
    assert "FLIGHT_COUNT" in codes(menon_trip, cat)


def test_not_enough_seats(menon_trip, cat):
    menon_trip["traveler"]["child_ages"] = [6] * 9
    menon_trip["traveler"]["children"] = 9
    assert "FLIGHT_SEATS" in codes(menon_trip, cat)


# --- airport transfers -------------------------------------------------------


def test_pickup_less_than_60_minutes_after_landing(menon_trip, cat):
    set_transfer_times(menon_trip, "i2", "2027-04-10T11:00", cat)
    assert "PICKUP_AFTER_LANDING" in codes(menon_trip, cat)


def test_airport_reached_less_than_180_minutes_before_departure(menon_trip, cat):
    set_transfer_times(menon_trip, "i13", "2027-04-16T08:00", cat)
    assert "AIRPORT_BEFORE_DEPARTURE" in codes(menon_trip, cat)


def test_airport_pickup_outside_service_hours(menon_trip, cat):
    set_transfer_times(menon_trip, "i13", "2027-04-16T05:30", cat)  # taxi starts 06:00
    assert "SERVICE_HOURS" in codes(menon_trip, cat)


def test_airport_transfer_for_another_area(menon_trip, cat):
    item(menon_trip, "i2").update(catalog_id="TR-NRT-GNZ-TAXI", price_inr=14000)
    set_transfer_times(menon_trip, "i2", "2027-04-10T11:30", cat)
    retotal(menon_trip)
    assert "AIRPORT_TRANSFER" in codes(menon_trip, cat)


def test_missing_return_airport_transfer(menon_trip, cat):
    remove(menon_trip, "i13")
    assert "AIRPORT_TRANSFER" in codes(menon_trip, cat)


# --- transfers between cities ------------------------------------------------


def test_missing_city_change_transfer(menon_trip, cat):
    remove(menon_trip, "i8")
    assert "INTERCITY_TRANSFER" in codes(menon_trip, cat)


def test_city_change_transfer_outside_service_hours(menon_trip, cat):
    set_transfer_times(menon_trip, "i8", "2027-04-13T05:30", cat)  # trains from 06:00
    assert "SERVICE_HOURS" in codes(menon_trip, cat)


# --- hotels ------------------------------------------------------------------


def test_night_without_hotel(menon_trip, cat):
    set_hotel(menon_trip, "i9", "RM-KYO-004-B", "2027-04-13", "2027-04-15", 1, cat)
    assert "HOTEL_NIGHTS" in codes(menon_trip, cat)


def test_hotel_night_on_last_day(menon_trip, cat):
    set_hotel(menon_trip, "i9", "RM-KYO-004-B", "2027-04-13", "2027-04-17", 1, cat)
    assert "HOTEL_NIGHTS" in codes(menon_trip, cat)


def test_room_type_does_not_fit(menon_trip, cat):
    set_hotel(menon_trip, "i3", "RM-TYO-004-A", "2027-04-10", "2027-04-13", 1, cat)  # 1 TWIN
    assert "ROOM_FIT" in codes(menon_trip, cat)


def test_room_from_another_hotel(menon_trip, cat):
    item(menon_trip, "i3")["room_id"] = "RM-TYO-001-B"
    assert "ROOM_FIT" in codes(menon_trip, cat)


def test_night_with_too_few_rooms(menon_trip, cat):
    # RM-TYO-001-B has 0 rooms left on 2027-04-12
    set_hotel(menon_trip, "i3", "RM-TYO-001-B", "2027-04-10", "2027-04-13", 1, cat)
    assert "ROOM_AVAILABILITY" in codes(menon_trip, cat)


# --- attractions -------------------------------------------------------------


def test_attraction_in_another_city(menon_trip, cat):
    set_attraction(menon_trip, "i5", "ATT-KYO-003", "2027-04-11T10:00", cat)
    assert "ATTRACTION_CITY" in codes(menon_trip, cat)


def test_attraction_in_nara(menon_trip, cat):
    set_attraction(menon_trip, "i5", "ATT-NAR-001", "2027-04-11T10:00", cat)
    assert "ATTRACTION_CITY" in codes(menon_trip, cat)


def test_attraction_closed_on_that_weekday(menon_trip, cat):
    set_attraction(menon_trip, "i6", "ATT-TYO-005", "2027-04-12T10:00", cat)  # closed Mondays
    assert "ATTRACTION_OPEN" in codes(menon_trip, cat)


def test_attraction_on_a_closed_date(menon_trip, cat):
    remove(menon_trip, "i7")
    set_attraction(menon_trip, "i6", "ATT-TYO-002", "2027-04-12T09:00", cat)
    assert "ATTRACTION_OPEN" in codes(menon_trip, cat)


def test_visit_ends_after_closing(menon_trip, cat):
    set_attraction(menon_trip, "i5", "ATT-TYO-001", "2027-04-11T21:00", cat)  # closes 22:00, 120 min
    assert "ATTRACTION_OPEN" in codes(menon_trip, cat)


def test_visit_starts_before_opening(menon_trip, cat):
    set_attraction(menon_trip, "i5", "ATT-TYO-001", "2027-04-11T08:00", cat)  # opens 09:00
    assert "ATTRACTION_OPEN" in codes(menon_trip, cat)


def test_overlapping_visits(menon_trip, cat):
    set_attraction(menon_trip, "i7", "ATT-TYO-007", "2027-04-12T10:30", cat)
    assert "ATTRACTION_OVERLAP" in codes(menon_trip, cat)


def test_same_attraction_twice(menon_trip, cat):
    set_attraction(menon_trip, "i6", "ATT-TYO-001", "2027-04-12T10:00", cat)
    assert "ATTRACTION_REPEAT" in codes(menon_trip, cat)


def test_full_day_without_attraction(menon_trip, cat):
    remove(menon_trip, "i5")
    assert "ATTRACTION_DAY_COUNT" in codes(menon_trip, cat)


def test_full_day_with_three_attractions(menon_trip, cat):
    add_attraction(menon_trip, "ATT-TYO-015", "2027-04-12T17:00", cat)
    assert "ATTRACTION_DAY_COUNT" in codes(menon_trip, cat)


def test_attraction_on_last_day(menon_trip, cat):
    add_attraction(menon_trip, "ATT-KYO-002", "2027-04-16T10:00", cat)
    assert "ATTRACTION_LAST_DAY" in codes(menon_trip, cat)


def test_arrival_day_attraction_before_reaching_hotel(menon_trip, cat):
    set_attraction(menon_trip, "i4", "ATT-TYO-012", "2027-04-10T11:00", cat)  # hotel at 12:40
    assert "ATTRACTION_BEFORE_ARRIVAL" in codes(menon_trip, cat)


def test_change_day_attraction_before_reaching_city(menon_trip, cat):
    set_attraction(menon_trip, "i10", "ATT-KYO-006", "2027-04-13T11:00", cat)  # train arrives 12:15
    assert "ATTRACTION_BEFORE_ARRIVAL" in codes(menon_trip, cat)


# --- prices ------------------------------------------------------------------


def test_wrong_item_price(menon_trip, cat):
    item(menon_trip, "i3")["price_inr"] = int(item(menon_trip, "i3")["price_inr"] * 1.5)
    retotal(menon_trip)
    assert "PRICE" in codes(menon_trip, cat)


def test_wrong_quantity(menon_trip, cat):
    item(menon_trip, "i1").update(quantity=2, price_inr=25200 * 2)
    retotal(menon_trip)
    assert "QUANTITY" in codes(menon_trip, cat)


def test_wrong_total(menon_trip, cat):
    menon_trip["total_inr"] += 5000
    assert "TOTAL" in codes(menon_trip, cat)


@pytest.mark.parametrize("field", ["item_id", "type", "catalog_id", "price_inr", "start"])
def test_item_missing_a_required_field(menon_trip, cat, field):
    del item(menon_trip, "i5")[field]
    assert "FORMAT" in codes(menon_trip, cat)
