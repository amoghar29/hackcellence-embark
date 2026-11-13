"""Rule-breaking edits of the hand-built valid Menon package (tests/fixtures/menon_trip.json).

Each mutation breaks exactly one travel rule (section 4) and names the rule code the app's
validator must report. The same mutations run against check_trip.py, so the independent
judge used by the API tests is itself tested.

Fixture items (Tokyo nights 10-12, Kyoto nights 13-15):
  i1 arrival flight FL-401 BLR->NRT lands 2027-04-10 10:30
  i2 arrival taxi NRT->Ueno 11:30-12:40      i3 Tokyo hotel (Ueno)
  i4 arrival day ATT-TYO-001 14:00-16:00
  i5 04-11 ATT-TYO-004 09:00-10:00          i6 04-11 ATT-TYO-007 11:00-12:30
  i7 04-12 (Monday) ATT-TYO-008 09:00-10:30 i8 train Tokyo->Kyoto 04-13 10:00-12:15
  i9 Kyoto hotel                            i10 change day ATT-KYO-003 14:00-15:00
  i11 04-14 ATT-KYO-001 09:00-10:30         i12 04-14 ATT-KYO-002 11:00-13:00
  i13 04-15 ATT-KYO-004 09:00-10:00         i14 return taxi Kyoto->KIX 04-16 07:00-08:30
  i15 return flight FL-411 KIX dep 12:00
"""
from datetime import datetime, timedelta

from tests.check_trip import load_catalog

J = load_catalog()  # the JSON catalog, independent of the app
ADULTS, CHILDREN = 2, 1
MUTATIONS = {}  # name -> (rule code the app validator reports, mutate(trip))


def mutation(code):
    def register(fn):
        MUTATIONS[fn.__name__] = (code, fn)
        return fn
    return register


# ---------- helpers ----------

def item(trip, item_id):
    return next(i for i in trip["items"] if i["item_id"] == item_id)


def retotal(trip):
    trip["total_inr"] = sum(i["price_inr"] for i in trip["items"])


def remove(trip, item_id):
    trip["items"] = [i for i in trip["items"] if i["item_id"] != item_id]
    retotal(trip)


def fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def set_flight(trip, item_id, flight_id):
    f = J["flights"][flight_id]
    item(trip, item_id).update(catalog_id=flight_id, start=f["departure_local"][:16], end=f["arrival_local"][:16],
                               price_inr=f["price_per_seat"]["amount"] * (ADULTS + CHILDREN))
    retotal(trip)


def attraction_fields(attraction_id, start):
    a = J["attractions"][attraction_id]
    s = datetime.fromisoformat(start)
    child = (a.get("child_price") or a["price_per_person"])["amount"]
    return dict(catalog_id=attraction_id, name=a["name"], city=a["city"], start=start,
                end=fmt(s + timedelta(minutes=a["visit_minutes"])), quantity=ADULTS + CHILDREN,
                price_inr=ADULTS * a["price_per_person"]["amount"] + CHILDREN * child)


def set_attraction(trip, item_id, attraction_id, start):
    item(trip, item_id).update(attraction_fields(attraction_id, start))
    retotal(trip)


def add_attraction(trip, attraction_id, start):
    trip["items"].append(dict(item_id=f"x{len(trip['items']) + 1}", type="attraction", status="PLANNED",
                              room_id=None, booking=None, sources=[], warnings=[],
                              **attraction_fields(attraction_id, start)))
    retotal(trip)


def set_transfer_times(trip, item_id, start):
    it = item(trip, item_id)
    t = J["transfers"][it["catalog_id"]]
    it.update(start=start, end=fmt(datetime.fromisoformat(start) + timedelta(minutes=t["duration_minutes"])))


def set_hotel(trip, item_id, room_id, check_in, check_out, rooms):
    r = J["rooms"][room_id]
    h = J["hotels"][r["hotel_id"]]
    nights = (datetime.fromisoformat(check_out) - datetime.fromisoformat(check_in)).days
    item(trip, item_id).update(catalog_id=h["hotel_id"], name=h["name"], city=h["city"], room_id=room_id,
                               start=check_in, end=check_out, quantity=rooms,
                               price_inr=r["price_per_night"]["amount"] * rooms * nights)
    retotal(trip)


# ---------- dates and cities ----------

@mutation("DATES")
def trip_shorter_than_three_nights(trip):
    trip["end_date"] = "2027-04-12"


@mutation("CITY_NIGHTS")
def city_with_one_night(trip):
    set_hotel(trip, "i3", "RM-TYO-004-B", "2027-04-10", "2027-04-11", 1)
    set_hotel(trip, "i9", "RM-KYO-004-B", "2027-04-11", "2027-04-16", 1)


@mutation("CITY_REPEAT")
def city_used_twice(trip):
    set_hotel(trip, "i9", "RM-TYO-003-C", "2027-04-13", "2027-04-16", 1)


@mutation("CITY_COUNTRY")
def city_outside_the_country(trip):
    room = next(r for r in J["rooms"].values()
                if J["hotels"][r["hotel_id"]]["city"] == "Dubai" and r["max_children"] >= 1)
    set_hotel(trip, "i9", room["room_id"], "2027-04-13", "2027-04-16", 1)


# ---------- flights ----------

@mutation("FLIGHT_ARRIVAL")
def arrival_flight_lands_on_wrong_date(trip):
    set_flight(trip, "i1", "FL-402")  # BLR->NRT lands 04-11


@mutation("FLIGHT_ARRIVAL")
def arrival_airport_does_not_serve_first_city(trip):
    set_flight(trip, "i1", "FL-740")  # BLR->KIX lands 04-10; KIX does not serve Tokyo


@mutation("FLIGHT_RETURN")
def return_flight_on_wrong_date(trip):
    other = next(f for f in J["flights"].values()
                 if f["from"] == "KIX" and f["to"] == "BLR" and f["departure_local"][:10] == "2027-04-15")
    set_flight(trip, "i15", other["flight_id"])


@mutation("FLIGHT_COUNT")
def missing_return_flight(trip):
    remove(trip, "i15")


@mutation("FLIGHT_SEATS")
def not_enough_seats(trip):
    trip["traveler"]["child_ages"] = [6] * 9
    trip["traveler"]["children"] = 9


# ---------- airport transfers ----------

@mutation("PICKUP_AFTER_LANDING")
def pickup_less_than_60_minutes_after_landing(trip):
    set_transfer_times(trip, "i2", "2027-04-10T11:00")


@mutation("AIRPORT_BEFORE_DEPARTURE")
def airport_reached_less_than_180_minutes_before_departure(trip):
    set_transfer_times(trip, "i14", "2027-04-16T08:00")


@mutation("SERVICE_HOURS")
def airport_pickup_outside_service_hours(trip):
    set_transfer_times(trip, "i14", "2027-04-16T05:30")  # taxi starts 06:00


@mutation("AIRPORT_TRANSFER")
def airport_transfer_for_another_area(trip):
    item(trip, "i2").update(catalog_id="TR-NRT-GNZ-TAXI", price_inr=14000)  # Ginza; the hotel is in Ueno
    set_transfer_times(trip, "i2", "2027-04-10T11:30")
    retotal(trip)


@mutation("AIRPORT_TRANSFER")
def missing_return_airport_transfer(trip):
    remove(trip, "i14")


# ---------- transfers between cities ----------

@mutation("INTERCITY_TRANSFER")
def missing_city_change_transfer(trip):
    remove(trip, "i8")


@mutation("SERVICE_HOURS")
def city_change_transfer_outside_service_hours(trip):
    set_transfer_times(trip, "i8", "2027-04-13T05:30")  # trains from 06:00


# ---------- hotels ----------

@mutation("HOTEL_NIGHTS")
def night_without_hotel(trip):
    set_hotel(trip, "i9", "RM-KYO-004-B", "2027-04-13", "2027-04-15", 1)


@mutation("HOTEL_NIGHTS")
def hotel_night_on_last_day(trip):
    set_hotel(trip, "i9", "RM-KYO-004-B", "2027-04-13", "2027-04-17", 1)


@mutation("ROOM_FIT")
def room_type_does_not_fit(trip):
    set_hotel(trip, "i3", "RM-TYO-004-A", "2027-04-10", "2027-04-13", 1)  # 1 TWIN for 2 adults + 1 child


@mutation("ROOM_FIT")
def room_from_another_hotel(trip):
    item(trip, "i3")["room_id"] = "RM-TYO-001-B"


@mutation("ROOM_AVAILABILITY")
def night_with_too_few_rooms(trip):
    set_hotel(trip, "i3", "RM-TYO-001-B", "2027-04-10", "2027-04-13", 1)  # 0 left on 04-12


# ---------- attractions ----------

@mutation("ATTRACTION_CITY")
def attraction_in_another_city(trip):
    set_attraction(trip, "i5", "ATT-KYO-007", "2027-04-11T09:00")


@mutation("ATTRACTION_CITY")
def attraction_in_nara(trip):
    set_attraction(trip, "i5", "ATT-NAR-001", "2027-04-11T06:00")


@mutation("ATTRACTION_OPEN")
def attraction_closed_on_that_weekday(trip):
    set_attraction(trip, "i7", "ATT-TYO-005", "2027-04-12T10:00")  # closed Mondays


@mutation("ATTRACTION_OPEN")
def attraction_on_a_closed_date(trip):
    set_attraction(trip, "i7", "ATT-TYO-002", "2027-04-12T09:00")  # closed 2027-04-12


@mutation("ATTRACTION_OPEN")
def visit_ends_after_closing(trip):
    set_attraction(trip, "i7", "ATT-TYO-012", "2027-04-12T22:30")  # closes 23:00, 60 min


@mutation("ATTRACTION_OPEN")
def visit_starts_before_opening(trip):
    set_attraction(trip, "i7", "ATT-TYO-012", "2027-04-12T08:00")  # opens 09:00


@mutation("ATTRACTION_OVERLAP")
def overlapping_visits(trip):
    set_attraction(trip, "i5", "ATT-TYO-004", "2027-04-11T10:30")  # i6 starts 11:00


@mutation("ATTRACTION_REPEAT")
def same_attraction_twice(trip):
    set_attraction(trip, "i7", "ATT-TYO-001", "2027-04-12T10:00")  # i4 already visits it


@mutation("ATTRACTION_DAY_COUNT")
def full_day_without_attraction(trip):
    remove(trip, "i7")  # the only visit on 04-12


@mutation("ATTRACTION_DAY_COUNT")
def full_day_with_three_attractions(trip):
    add_attraction(trip, "ATT-TYO-015", "2027-04-11T17:00")  # 04-11 already has 2


@mutation("ATTRACTION_LAST_DAY")
def attraction_on_last_day(trip):
    add_attraction(trip, "ATT-KYO-006", "2027-04-16T10:00")


@mutation("ATTRACTION_BEFORE_ARRIVAL")
def arrival_day_attraction_before_reaching_hotel(trip):
    set_attraction(trip, "i4", "ATT-TYO-001", "2027-04-10T11:00")  # hotel reached 12:40


@mutation("ATTRACTION_BEFORE_ARRIVAL")
def change_day_attraction_before_reaching_city(trip):
    set_attraction(trip, "i10", "ATT-KYO-003", "2027-04-13T11:00")  # train arrives 12:15


# ---------- prices ----------

@mutation("PRICE")
def wrong_item_price(trip):
    item(trip, "i3")["price_inr"] = int(item(trip, "i3")["price_inr"] * 1.5)
    retotal(trip)


@mutation("PRICE")
def child_price_ignored(trip):
    item(trip, "i8")["price_inr"] = 3 * 7935  # train: children pay child_price 3968
    retotal(trip)


@mutation("PRICE")
def per_vehicle_priced_per_person(trip):
    item(trip, "i2")["price_inr"] = 3 * 12880  # taxi: 1 vehicle for 3 travelers
    retotal(trip)


@mutation("QUANTITY")
def wrong_quantity(trip):
    item(trip, "i1").update(quantity=2, price_inr=25200 * 2)
    retotal(trip)


@mutation("TOTAL")
def wrong_total(trip):
    trip["total_inr"] += 5000
