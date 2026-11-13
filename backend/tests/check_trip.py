"""Checks an exported trip JSON against every travel rule (handout section 4).

Usage (from backend/): python tests/check_trip.py trip.json [--edited]
--edited skips "first package has 1-2 attractions on every full day" (only applies to the first package).
Returns a list of (RULE_CODE, message); empty list = package is correct.
"""
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[2] / "data/hackathon-problem-1-holiday-package/data/catalog"
DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def load_catalog(d=CATALOG):
    j = lambda n: json.loads((Path(d) / f"{n}.json").read_text(encoding="utf-8"))
    return {
        "dest": j("destinations"),
        "airports": {a["code"]: a for a in j("airports")},
        "flights": {f["flight_id"]: f for f in j("flights")},
        "hotels": {h["hotel_id"]: h for h in j("hotels")},
        "rooms": {r["room_id"]: r for r in j("rooms")},
        "avail": {(a["room_id"], a["date"]): a["rooms_left"] for a in j("availability")},
        "transfers": {t["transfer_id"]: t for t in j("transfers")},
        "attractions": {a["attraction_id"]: a for a in j("attractions")},
    }


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def in_window(dt, frm, until):
    """Both ends included; '24:00' = end of day; until < from = runs past midnight."""
    t, f, u = dt.hour * 60 + dt.minute, mins(frm), mins(until)
    if f <= u:
        return f <= t <= u or (u == 1440 and t == 0)
    return t >= f or t <= u


def nights(ci, co):
    return [ci + timedelta(n) for n in range((co - ci).days)]


def transfer_price(t, a, c):
    if t["pricing"] == "PER_PERSON":
        return a * t["price"]["amount"] + c * (t.get("child_price") or t["price"])["amount"]
    return t["price"]["amount"] * math.ceil((a + c) / t["max_passengers"])


def check(trip, cat, first_package=True):
    v = []
    bad = lambda code, msg: v.append((code, msg))
    dt = lambda s: datetime.fromisoformat(s)
    d = lambda s: date.fromisoformat(s[:10])

    def price(it, expected):
        if abs(it["price_inr"] - expected) > 0.01 * expected:
            bad("PRICE_ITEM", f"{it['item_id']} price {it['price_inr']} != {expected}")

    # --- travelers, country, dates ---
    tr = trip["traveler"]
    A, ages = tr["adults"], tr.get("child_ages") or []
    C = len(ages)
    N = A + C
    if A < 1 or tr.get("children", C) != C or any(not 0 <= x <= 17 for x in ages):
        bad("TRAVELERS", f"adults={A} children={tr.get('children')} ages={ages}")
    country = next((c for c in cat["dest"]["countries"] if c["name"] == trip.get("country")), None)
    if not country:
        bad("COUNTRY", f"unknown country {trip.get('country')!r}")
        return v
    cities = {c["name"] for c in country["cities"]}
    rules = cat["dest"]["rules"]
    start, end = d(trip["start_date"]), d(trip["end_date"])
    if not rules["min_nights"] <= (end - start).days <= rules["max_nights"]:
        bad("TRIP_NIGHTS", f"{(end - start).days} nights")
    if start < d(rules["data_window"]["first_night"]) or end > d(rules["data_window"]["last_departure"]):
        bad("TRIP_WINDOW", f"{start}..{end} outside data window")

    # --- resolve items against the catalog ---
    table = {"flight": "flights", "hotel": "hotels", "transfer": "transfers", "attraction": "attractions"}
    by = defaultdict(list)
    ids = [it["item_id"] for it in trip["items"]]
    if len(ids) != len(set(ids)):
        bad("FORMAT", "item_id not unique")
    for it in trip["items"]:
        rec = cat[table[it["type"]]].get(it["catalog_id"]) if it["type"] in table else None
        if rec is None:
            bad("UNKNOWN_ID", f"{it['item_id']}: {it['type']} {it.get('catalog_id')}")
        else:
            by[it["type"]].append((it, rec))
    total = sum(it["price_inr"] for it in trip["items"])
    if abs(trip["total_inr"] - total) > 0.01 * total:
        bad("PRICE_TOTAL", f"total_inr {trip['total_inr']} != sum of items {total}")

    # --- hotels ---
    stays = []  # one per city: dict(city, hotel, room_id, k, ci, co)
    night_count = Counter()
    for it, h in sorted(by["hotel"], key=lambda x: x[0]["start"]):
        ci, co, k = d(it["start"]), d(it["end"]), it["quantity"]
        room = cat["rooms"].get(it.get("room_id"))
        if h["city"] not in cities:
            bad("CITY_COUNTRY", f"{h['hotel_id']} is in {h['city']}")
        if not room or room["hotel_id"] != h["hotel_id"]:
            bad("HOTEL_ROOM", f"{it['item_id']}: room {it.get('room_id')} not in {h['hotel_id']}")
            continue
        night_count.update(nights(ci, co))
        if not (A <= k * room["max_adults"] and N <= k * (room["max_adults"] + room["max_children"]) and A >= k):
            bad("HOTEL_FIT", f"{k} x {room['room_id']} does not fit {A}A+{C}C")
        for n in nights(ci, co):
            if cat["avail"].get((room["room_id"], n.isoformat()), 0) < k:
                bad("HOTEL_ROOMS_LEFT", f"{room['room_id']} on {n}: fewer than {k} rooms left")
        price(it, room["price_per_night"]["amount"] * k * len(nights(ci, co)))
        last = stays[-1] if stays else None
        if last and last["city"] == h["city"] and last["co"] == ci:  # same city split into several items
            if (last["hotel"]["hotel_id"], last["room_id"], last["k"]) != (h["hotel_id"], room["room_id"], k):
                bad("HOTEL_ONE_PER_CITY", f"{h['city']}: more than one hotel/room type")
            last["co"] = co
        else:
            stays.append(dict(city=h["city"], hotel=h, room_id=room["room_id"], k=k, ci=ci, co=co))
    trip_nights = nights(start, end)
    if set(night_count) != set(trip_nights) or any(c != 1 for c in night_count.values()):
        bad("HOTEL_NIGHTS", f"hotel nights {sorted(night_count.items())} != one each for {trip_nights}")
    for city, n in Counter(s["city"] for s in stays).items():
        if n > 1:
            bad("CITY_ONCE", f"{city} appears {n} times")
    for s in stays:
        if (s["co"] - s["ci"]).days < rules["min_nights_per_city"]:
            bad("CITY_MIN_NIGHTS", f"{s['city']}: {(s['co'] - s['ci']).days} nights")
    if not stays:
        return v
    night_city = {n: s["city"] for s in stays for n in nights(s["ci"], s["co"])}
    changes = {stays[i + 1]["ci"]: (stays[i]["city"], stays[i + 1]["city"]) for i in range(len(stays) - 1)}

    # --- flights ---
    home = tr["home_airport"]
    af = rf = None
    out = [f for _, f in by["flight"] if f["from"] == home]
    back = [f for _, f in by["flight"] if f["to"] == home]
    if len(by["flight"]) != 2 or len(out) != 1 or len(back) != 1:
        bad("FLIGHT_COUNT", f"need 1 flight from and 1 back to {home}")
    else:
        af, rf = out[0], back[0]
        if d(af["arrival_local"]) != start:
            bad("FLIGHT_ARRIVAL_DATE", f"{af['flight_id']} lands {af['arrival_local']}, start {start}")
        if stays[0]["city"] not in cat["airports"][af["to"]].get("serves_cities", []):
            bad("FLIGHT_ARRIVAL_AIRPORT", f"{af['to']} does not serve {stays[0]['city']}")
        if d(rf["departure_local"]) != end:
            bad("FLIGHT_RETURN_DATE", f"{rf['flight_id']} leaves {rf['departure_local']}, end {end}")
        if stays[-1]["city"] not in cat["airports"][rf["from"]].get("serves_cities", []):
            bad("FLIGHT_RETURN_AIRPORT", f"{rf['from']} does not serve {stays[-1]['city']}")
    for it, f in by["flight"]:
        if f["seats_left"] < N:
            bad("FLIGHT_SEATS", f"{f['flight_id']}: {f['seats_left']} seats < {N}")
        price(it, f["price_per_seat"]["amount"] * N)

    # --- transfers ---
    reach = {}  # day -> datetime the traveler reaches that night's city
    air = sorted([x for x in by["transfer"] if x[1].get("airport")], key=lambda x: x[0]["start"])
    inter = [x for x in by["transfer"] if x[1].get("from_city")]
    for it, t in by["transfer"]:
        price(it, transfer_price(t, A, C))
        if not in_window(dt(it["start"]), t["service_from"], t["service_until"]):
            bad("TRANSFER_HOURS", f"{it['item_id']} pickup {it['start']} outside {t['service_from']}-{t['service_until']}")
    if len(air) != 2:
        bad("AIRPORT_TRANSFER_COUNT", f"{len(air)} airport transfers, need 2")
    elif af and rf:
        (ai, at), (ri, rt) = air
        for t, ap, hotel, leg in ((at, af["to"], stays[0]["hotel"], "arrival"), (rt, rf["from"], stays[-1]["hotel"], "return")):
            if t["airport"] != ap or t["city"] != hotel["city"] or t["area"] not in (None, hotel["area"]):
                bad("AIRPORT_TRANSFER_MATCH", f"{leg} {t['transfer_id']} does not link {ap} and {hotel['hotel_id']}")
        if dt(ai["start"]) < dt(af["arrival_local"]) + timedelta(minutes=60):
            bad("AIRPORT_PICKUP_60", f"pickup {ai['start']} < landing {af['arrival_local']} + 60m")
        if dt(ri["start"]) + timedelta(minutes=rt["duration_minutes"]) > dt(rf["departure_local"]) - timedelta(minutes=180):
            bad("AIRPORT_ARRIVE_180", f"reaches airport later than 180m before {rf['departure_local']}")
        reach[start] = dt(ai["start"]) + timedelta(minutes=at["duration_minutes"])
    for it, t in inter:
        day = d(it["start"])
        if changes.get(day) != (t["from_city"], t["to_city"]):
            bad("INTERCITY_MATCH", f"{t['transfer_id']} on {day} does not match city change {changes.get(day)}")
        reach[day] = dt(it["start"]) + timedelta(minutes=t["duration_minutes"])
    per_day = Counter(d(it["start"]) for it, _ in inter)
    for day in changes:
        if per_day[day] != 1:
            bad("INTERCITY_COUNT", f"{day}: {per_day[day]} transfers between cities, need 1")

    # --- attractions ---
    visits = defaultdict(list)
    for aid, n in Counter(a["attraction_id"] for _, a in by["attraction"]).items():
        if n > 1:
            bad("ATT_DUPLICATE", f"{aid} {n} times")
    for it, a in by["attraction"]:
        s = dt(it["start"])
        e = s + timedelta(minutes=a["visit_minutes"])
        day = s.date()
        price(it, A * a["price_per_person"]["amount"] + C * (a.get("child_price") or a["price_per_person"])["amount"])
        if day >= end or day < start:
            bad("ATT_LAST_DAY", f"{a['attraction_id']} on {day}: no attractions on the last day or outside the trip")
            continue
        if a["city"] != night_city.get(day):
            bad("ATT_CITY", f"{a['attraction_id']} in {a['city']}, hotel that night in {night_city.get(day)}")
        if DAYS[day.weekday()] not in a["open_days"] or day.isoformat() in a.get("closed_dates", []):
            bad("ATT_OPEN_DAY", f"{a['attraction_id']} closed on {day}")
        sm = s.hour * 60 + s.minute
        if sm < mins(a["open_from"]) or sm + a["visit_minutes"] > mins(a["open_until"]):
            bad("ATT_HOURS", f"{a['attraction_id']} {s.time()}+{a['visit_minutes']}m outside {a['open_from']}-{a['open_until']}")
        if day in reach and s < reach[day]:
            bad("ATT_BEFORE_ARRIVAL", f"{a['attraction_id']} starts {s} before reaching city {reach[day]}")
        visits[day].append((s, e, a["attraction_id"]))
    for day, vs in visits.items():
        vs.sort()
        for (s1, e1, a1), (s2, _, a2) in zip(vs, vs[1:]):
            if s2 < e1:
                bad("ATT_OVERLAP", f"{a1} and {a2} overlap on {day}")
    if first_package:
        for day in trip_nights[1:]:
            if day not in changes and not 1 <= len(visits[day]) <= 2:
                bad("ATT_FULL_DAY_COUNT", f"{day}: {len(visits[day])} attractions, need 1-2")
    return v


if __name__ == "__main__":
    trip = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    problems = check(trip, load_catalog(), first_package="--edited" not in sys.argv)
    for code, msg in problems:
        print(f"FAIL {code}: {msg}")
    print("OK: all rules pass" if not problems else f"{len(problems)} rule violation(s)")
    sys.exit(1 if problems else 0)
