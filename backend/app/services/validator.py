"""Checks a package against every travel rule in handout section 4.

validate(trip, cat) -> list of "CODE: message"; an empty list means the package is correct.
Nothing is saved or returned by the app without passing this. All times are local to the
destination, so they are compared directly; flight times come from the catalog, never from arithmetic.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from app.core.timeutil import DAYS, in_window, minute_of_day, parse_hhmm
from app.services import pricing

TYPES = ("flight", "hotel", "transfer", "attraction")
REQUIRED_ITEM = ("item_id", "type", "catalog_id", "start", "quantity", "price_inr")


def _nights(check_in, check_out):
    return [check_in + timedelta(n) for n in range((check_out - check_in).days)]


def validate(trip, cat, first_package=True):
    v = []
    bad = lambda code, msg: v.append(f"{code}: {msg}")
    d = lambda s: date.fromisoformat(s[:10])
    dt = datetime.fromisoformat

    def price(it, expected):
        if abs(it["price_inr"] - expected) > 0.01 * expected:
            bad("PRICE", f"{it['item_id']} costs {it['price_inr']}, expected {expected}")

    def quantity(it, expected):
        if it["quantity"] != expected:
            bad("QUANTITY", f"{it['item_id']} has quantity {it['quantity']}, expected {expected}")

    # ---------- travelers, country, dates ----------
    tr = trip["traveler"]
    A, ages = tr["adults"], tr.get("child_ages") or []
    C = len(ages)
    N = A + C
    if A < 1 or tr.get("children", C) != C or any(not 0 <= x <= 17 for x in ages):
        bad("TRAVELERS", f"adults={A}, children={tr.get('children')}, ages={ages}")
    country = next((c for c in cat.destinations["countries"] if c["name"] == trip.get("country")), None)
    if not country:
        return v + [f"COUNTRY: unknown country {trip.get('country')!r}"]
    cities = {c["name"] for c in country["cities"]}
    rules = cat.destinations["rules"]
    start, end = d(trip["start_date"]), d(trip["end_date"])
    if not rules["min_nights"] <= (end - start).days <= rules["max_nights"]:
        bad("DATES", f"the trip has {(end - start).days} nights")
    if start < d(rules["data_window"]["first_night"]) or end > d(rules["data_window"]["last_departure"]):
        bad("DATES", f"{start} to {end} is outside the data window")

    # ---------- items against the catalog ----------
    by = defaultdict(list)
    for it in trip["items"]:
        missing = [f for f in REQUIRED_ITEM if it.get(f) is None]
        rec = getattr(cat, f"get_{it['type']}")(it.get("catalog_id")) if it.get("type") in TYPES else None
        if missing or rec is None:
            bad("FORMAT", f"item {it.get('item_id')}: missing {missing} or unknown {it.get('type')} {it.get('catalog_id')}")
        else:
            by[it["type"]].append((it, rec))
    ids = [it.get("item_id") for it in trip["items"]]
    if len(ids) != len(set(ids)):
        bad("FORMAT", "item_id is not unique")
    total = sum(it.get("price_inr") or 0 for it in trip["items"])
    if abs(trip["total_inr"] - total) > 0.01 * total:
        bad("TOTAL", f"total_inr {trip['total_inr']} is not the sum of the items {total}")

    # ---------- hotels: one stay per city ----------
    stays = []
    night_count = Counter()
    for it, h in sorted(by["hotel"], key=lambda x: x[0]["start"]):
        ci, co, k = d(it["start"]), d(it["end"]), it["quantity"]
        if h["city"] not in cities:
            bad("CITY_COUNTRY", f"{h['name']} is in {h['city']}, not in {country['name']}")
        night_count.update(_nights(ci, co))
        stays.append({"city": h["city"], "hotel": h, "ci": ci, "co": co})
        room = cat.get_room(it.get("room_id"))
        if not room or room["hotel_id"] != h["hotel_id"]:
            bad("ROOM_FIT", f"{it['item_id']}: room {it.get('room_id')} is not a room of {h['hotel_id']}")
            continue
        if not (k >= 1 and A <= k * room["max_adults"] and A >= k
                and N <= k * (room["max_adults"] + room["max_children"])):
            bad("ROOM_FIT", f"{k} x {room['room_id']} does not fit {A} adults and {C} children")
        for n in _nights(ci, co):
            if cat.rooms_left(room["room_id"], n) < k:
                bad("ROOM_AVAILABILITY", f"{room['room_id']} has fewer than {k} rooms left on {n}")
        price(it, pricing.hotel_price(room, k, len(_nights(ci, co))))
    trip_nights = _nights(start, end)
    if set(night_count) != set(trip_nights) or any(c != 1 for c in night_count.values()):
        bad("HOTEL_NIGHTS", f"need exactly one hotel on each night from {start} to the night before {end}")
    for city, n in Counter(s["city"] for s in stays).items():
        if n > 1:
            bad("CITY_REPEAT", f"{city} appears {n} times in the plan")
    for s in stays:
        if (s["co"] - s["ci"]).days < rules["min_nights_per_city"]:
            bad("CITY_NIGHTS", f"{s['city']} has {(s['co'] - s['ci']).days} night(s)")
    if not stays:
        return v
    night_city = {n: s["city"] for s in stays for n in _nights(s["ci"], s["co"])}
    changes = {b["ci"]: (a["city"], b["city"]) for a, b in zip(stays, stays[1:])}

    # ---------- flights ----------
    home = tr["home_airport"]
    af = rf = None
    out = [f for _, f in by["flight"] if f["from_airport"] == home]
    back = [f for _, f in by["flight"] if f["to_airport"] == home]
    if len(by["flight"]) != 2 or len(out) != 1 or len(back) != 1:
        bad("FLIGHT_COUNT", f"need one flight from {home} and one back to {home}")
    else:
        af, rf = out[0], back[0]
        if af["arrival_local"].date() != start:
            bad("FLIGHT_ARRIVAL", f"{af['flight_id']} lands on {af['arrival_local'].date()}, the trip starts {start}")
        if not cat.serves(af["to_airport"], stays[0]["city"]):
            bad("FLIGHT_ARRIVAL", f"{af['to_airport']} does not serve {stays[0]['city']}")
        if rf["departure_local"].date() != end:
            bad("FLIGHT_RETURN", f"{rf['flight_id']} leaves on {rf['departure_local'].date()}, the trip ends {end}")
        if not cat.serves(rf["from_airport"], stays[-1]["city"]):
            bad("FLIGHT_RETURN", f"{rf['from_airport']} does not serve {stays[-1]['city']}")
    for it, f in by["flight"]:
        if f["seats_left"] < N:
            bad("FLIGHT_SEATS", f"{f['flight_id']} has {f['seats_left']} seats left, {N} needed")
        quantity(it, N)
        price(it, pricing.flight_price(f, N))

    # ---------- transfers ----------
    reach = {}  # day -> local time the traveler reaches that night's city
    for it, t in by["transfer"]:
        quantity(it, pricing.transfer_quantity(t, A, C))
        price(it, pricing.transfer_price(t, A, C))
        if not in_window(minute_of_day(dt(it["start"])), t["service_from"], t["service_until"]):
            bad("SERVICE_HOURS", f"{it['item_id']} pickup {it['start']} is outside {t['service_from']}-{t['service_until']}")
    air = sorted((x for x in by["transfer"] if x[1]["airport"]), key=lambda x: x[0]["start"])
    if len(air) != 2:
        bad("AIRPORT_TRANSFER", f"{len(air)} airport transfer(s), need one on arrival and one on return")
    elif af and rf:
        (ai, at), (ri, rt) = air
        for t, airport, hotel in ((at, af["to_airport"], stays[0]["hotel"]), (rt, rf["from_airport"], stays[-1]["hotel"])):
            if t["airport"] != airport or t["city"] != hotel["city"] or t["area"] not in (None, hotel["area"]):
                bad("AIRPORT_TRANSFER", f"{t['transfer_id']} does not link {airport} and {hotel['name']} ({hotel['area']})")
        if dt(ai["start"]) < af["arrival_local"] + timedelta(minutes=60):
            bad("PICKUP_AFTER_LANDING", f"pickup {ai['start']} is less than 60 minutes after landing")
        at_airport = dt(ri["start"]) + timedelta(minutes=rt["duration_minutes"])
        if at_airport > rf["departure_local"] - timedelta(minutes=180):
            bad("AIRPORT_BEFORE_DEPARTURE", f"reaches the airport at {at_airport}, less than 180 minutes before departure")
        reach[start] = dt(ai["start"]) + timedelta(minutes=at["duration_minutes"])
    inter = [x for x in by["transfer"] if x[1]["from_city"]]
    per_day = Counter()
    for it, t in inter:
        day = d(it["start"])
        if changes.get(day) != (t["from_city"], t["to_city"]):
            bad("INTERCITY_TRANSFER", f"{t['transfer_id']} on {day} does not match a city change")
        else:
            per_day[day] += 1
            reach[day] = dt(it["start"]) + timedelta(minutes=t["duration_minutes"])
    for day, (a, b) in changes.items():
        if per_day[day] != 1:
            bad("INTERCITY_TRANSFER", f"{day}: need exactly one transfer from {a} to {b}")

    # ---------- attractions ----------
    visits = defaultdict(list)
    for aid, n in Counter(a["attraction_id"] for _, a in by["attraction"]).items():
        if n > 1:
            bad("ATTRACTION_REPEAT", f"{aid} is in the package {n} times")
    for it, a in by["attraction"]:
        s = dt(it["start"])
        day = s.date()
        quantity(it, N)
        price(it, pricing.attraction_price(a, A, C))
        if not start <= day < end:
            bad("ATTRACTION_LAST_DAY", f"{a['name']} on {day}: no visits on the last day or outside the trip")
            continue
        if a["city"] != night_city.get(day):
            bad("ATTRACTION_CITY", f"{a['name']} is in {a['city']}; the hotel that night is in {night_city.get(day)}")
        if DAYS[day.weekday()] not in a["open_days"] or day in a["closed_dates"]:
            bad("ATTRACTION_OPEN", f"{a['name']} is closed on {day}")
        m = minute_of_day(s)
        if m < parse_hhmm(a["open_from"]) or m + a["visit_minutes"] > parse_hhmm(a["open_until"]):
            bad("ATTRACTION_OPEN", f"{a['name']}: a {a['visit_minutes']}-minute visit at {s.time()} is outside "
                                   f"{a['open_from']}-{a['open_until']}")
        if day in reach and s < reach[day]:
            bad("ATTRACTION_BEFORE_ARRIVAL", f"{a['name']} starts at {s}, before the traveler arrives at {reach[day]}")
        visits[day].append((s, s + timedelta(minutes=a["visit_minutes"]), a["name"]))
    for day, vs in visits.items():
        vs.sort()
        for (_, e1, n1), (s2, _, n2) in zip(vs, vs[1:]):
            if s2 < e1:
                bad("ATTRACTION_OVERLAP", f"{n1} and {n2} overlap on {day}")
    if first_package:
        for day in trip_nights[1:]:
            if day not in changes and not 1 <= len(visits[day]) <= 2:
                bad("ATTRACTION_DAY_COUNT", f"{day} has {len(visits[day])} attractions; a full day needs 1 or 2")
    return v
