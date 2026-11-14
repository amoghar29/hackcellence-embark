"""Turns a selection (which flights, rooms, transfers and visits, and when) into the Package of docs/API.md.

A selection is what the builder chooses and what the database stores:
  {"arrival": {"flight_id", "transfer_id", "pickup"}, "return": {...same},
   "stays": [{"hotel_id", "room_id", "rooms", "check_in", "check_out"}],      in city order
   "intercity": [{"transfer_id", "pickup"}], "attractions": [{"attraction_id", "start"}]}
Names, prices and details always come from the catalog, so a package read back from the database is identical.
Item ids say what the item is (flight-arrival, hotel-1, attraction-ATT-TYO-001) and stay the same when
another item is changed or removed.
"""
from datetime import date, timedelta

from app.core.timeutil import at, fmt
from app.services import pricing, travel
from app.services.travel import DAY_END


def travel_minutes(items):
    """Flight durations plus the transfers between cities (G4 "fastest"). Airport transfers do not count."""
    return sum(i["details"]["duration_minutes"] for i in items
               if i["type"] == "flight" or i["details"].get("kind") == "INTERCITY")


def avg_stars(items):
    """Hotel stars averaged per night (G4 "best rated"). The guest rating does not count."""
    hotels = [i["details"] for i in items if i["type"] == "hotel"]
    return sum(h["stars"] * h["nights"] for h in hotels) / sum(h["nights"] for h in hotels)


def _reach_times(selection, cat):
    """Local time the traveler gets to each stay: after the airport transfer, or after the transfer from the last city."""
    legs = [selection["arrival"]] + selection["intercity"]
    return [leg["pickup"] + timedelta(minutes=cat.get_transfer(leg["transfer_id"])["duration_minutes"]) for leg in legs]


def day_legs(selection, cat):
    """{attraction_id: {"travel_from", "travel_back" (last visit of the day only), "warnings"}}.
    A leg is {name, lat, lng, minutes, km, source}: where the traveler comes from (the previous visit that day,
    else the hotel of that night) or goes back to. A gap shorter than the travel time, or getting back to
    the hotel after DAY_END, is a warning (G1), never a refusal: travel time is not a travel rule."""
    move = travel.for_catalog(cat)
    hotels = [(s["check_in"], s["check_out"], cat.get_hotel(s["hotel_id"])) for s in selection["stays"]]
    by_day = {}
    for v in sorted(selection["attractions"], key=lambda v: v["start"]):
        by_day.setdefault(v["start"].date(), []).append((v, cat.get_attraction(v["attraction_id"])))
    leg = lambda a, b: {"name": a["name"], "lat": a["lat"], "lng": a["lng"], **move.leg(a, b)}
    out = {}
    for day, visits in by_day.items():
        hotel = next((h for ci, co, h in hotels if ci <= day < co), None)
        here, free = hotel, None
        for v, a in visits:
            w, came = [], here and leg(here, a)
            if came and free and v["start"] < free + timedelta(minutes=came["minutes"]):
                gap = (v["start"] - free) // timedelta(minutes=1)
                w.append(f"Only {max(gap, 0)} min after {here['name']}; getting here takes about "
                         f"{came['minutes']} min.")
            out[a["attraction_id"]] = {"travel_from": came, "travel_back": None, "warnings": w}
            here, free = a, v["start"] + timedelta(minutes=a["visit_minutes"] + travel.overrun(a))
        if hotel:
            back = {"name": hotel["name"], "lat": hotel["lat"], "lng": hotel["lng"], **move.leg(here, hotel)}
            out[here["attraction_id"]]["travel_back"] = back
            home = free + timedelta(minutes=back["minutes"])
            if home > at(day, DAY_END):
                out[here["attraction_id"]]["warnings"].append(
                    f"You get back to {hotel['name']} at about {home:%H:%M}, after {DAY_END}.")
    return out


def assemble(request, selection, cat, reference=None):
    A, C = request["adults"], len(request["child_ages"])
    N = A + C
    home = request["departure_city"]
    tz = cat.country(request["country"])["timezone"]
    status = "BOOKED" if reference else "PLANNED"
    items = []

    def add(item_id, type_, name, city, catalog_id, start, end, quantity, price, details, room_id=None, **extra):
        items.append({"item_id": item_id, "type": type_, "name": name, "city": city, "status": status,
                      "catalog_id": catalog_id, "room_id": room_id, "start": start, "end": end,
                      "quantity": quantity, "price_inr": price,
                      "booking": {"reference": reference} if reference else None,
                      "sources": [], "warnings": [], "details": details, **extra})

    stays = selection["stays"]
    hotels = [cat.get_hotel(s["hotel_id"]) for s in stays]

    for direction, leg, city in (("ARRIVAL", selection["arrival"], hotels[0]["city"]),
                                 ("RETURN", selection["return"], cat.home_city(home))):
        f = cat.get_flight(leg["flight_id"])
        add(f"flight-{direction.lower()}", "flight", f"{f['flight_number']} {f['from_airport']} to {f['to_airport']}", city, f["flight_id"],
            fmt(f["departure_local"]), fmt(f["arrival_local"]), N, pricing.flight_price(f, N),
            {"direction": direction, "airline": f["airline"], "flight_number": f["flight_number"],
             "from_airport": f["from_airport"], "to_airport": f["to_airport"], "stops": f["stops"],
             # the catalog's elapsed time (time-zone change and layover included), never arrival minus departure
             "duration_minutes": f["duration_minutes"], "price_per_seat_inr": f["price_inr"]})

    transfers = [("transfer-arrival", "AIRPORT_ARRIVAL", selection["arrival"]),
                 ("transfer-return", "AIRPORT_RETURN", selection["return"])]
    transfers += [(f"transfer-city-{n}", "INTERCITY", leg) for n, leg in enumerate(selection["intercity"], 1)]
    for item_id, kind, leg in transfers:
        t = cat.get_transfer(leg["transfer_id"])
        add(item_id, "transfer", t["name"], t["city"] or t["to_city"], t["transfer_id"], fmt(leg["pickup"]),
            fmt(leg["pickup"] + timedelta(minutes=t["duration_minutes"])), pricing.transfer_quantity(t, A, C),
            pricing.transfer_price(t, A, C),
            {"kind": kind, "transfer_type": t["type"], "from_point": t["from_point"], "to_point": t["to_point"],
             "duration_minutes": t["duration_minutes"], "pricing": t["pricing"]})

    reach = _reach_times(selection, cat)
    for n, (s, h) in enumerate(zip(stays, hotels), 1):
        room = cat.get_room(s["room_id"])
        nights = (s["check_out"] - s["check_in"]).days
        # G1: check-in times are display-only for the judges, so an early arrival is a warning, not a refusal
        early = reach[n - 1].date() == s["check_in"] and f"{reach[n - 1]:%H:%M}" < h["check_in_from"]
        warnings = [f"You reach {h['name']} at {reach[n - 1]:%H:%M}, before check-in from {h['check_in_from']}. "
                    "Ask for early check-in or luggage storage."] if early else []
        add(f"hotel-{n}", "hotel", h["name"], h["city"], h["hotel_id"], s["check_in"].isoformat(), s["check_out"].isoformat(),
            s["rooms"], pricing.hotel_price(room, s["rooms"], nights),
            {"area": h["area"], "lat": h["lat"], "lng": h["lng"], "stars": h["stars"], "rating": h["rating"],
             "room_type": room["room_type"],
             "room_name": room["name"], "rooms": s["rooms"], "nights": nights, "price_per_night_inr": room["price_inr"],
             "check_in_from": h["check_in_from"], "check_out_until": h["check_out_until"], "image": "/" + h["image"]},
            room_id=room["room_id"], warnings=warnings)

    legs = day_legs(selection, cat)
    for visit in selection["attractions"]:
        a = cat.get_attraction(visit["attraction_id"])
        lg = legs[a["attraction_id"]]
        add(f"attraction-{a['attraction_id']}", "attraction", a["name"], a["city"], a["attraction_id"], fmt(visit["start"]),
            fmt(visit["start"] + timedelta(minutes=a["visit_minutes"])), N, pricing.attraction_price(a, A, C),
            {"category": a["category"], "visit_minutes": a["visit_minutes"], "open_from": a["open_from"],
             "open_until": a["open_until"], "child_friendly": a["child_friendly"], "image": "/" + a["image"],
             "lat": a["lat"], "lng": a["lng"], "travel_from": lg["travel_from"], "travel_back": lg["travel_back"]},
            warnings=lg["warnings"])

    items.sort(key=lambda i: (i["start"], i["item_id"]))
    total = sum(i["price_inr"] for i in items)
    trip = {
        "status": status, "reference": reference,
        "traveler": {"name": None, "home_airport": home, "adults": A, "children": C,
                     "child_ages": list(request["child_ages"])},
        "country": request["country"],
        "start_date": request["start_date"].isoformat(), "end_date": request["end_date"].isoformat(),
        "nights": request["nights"],
        "cities": [{"city": h["city"], "nights": (s["check_out"] - s["check_in"]).days,
                    "check_in": s["check_in"].isoformat(), "check_out": s["check_out"].isoformat()}
                   for s, h in zip(stays, hotels)],
        "budget_inr": request["budget_inr"], "total_inr": total, "remaining_inr": request["budget_inr"] - total,
        "travel_minutes": travel_minutes(items), "avg_stars": round(avg_stars(items), 2),
        "items": items,
    }
    trip["days"] = _days(trip, selection, cat, tz)
    return trip


def _days(trip, selection, cat, tz):
    """One entry per calendar date. Each event's time is local to where it happens; `timezone` says where."""
    start, end = trip["start_date"], trip["end_date"]
    events = {}  # date -> [(time, kind, item_id, title, timezone)]

    def event(when, kind, it, title, zone):
        events.setdefault(when[:10], []).append(
            {"time": when[11:16], "kind": kind, "item_id": it["item_id"], "title": title, "timezone": zone})

    reach_at, legs = _reach_times(selection, cat), [selection["arrival"]] + selection["intercity"]
    pickups = {}  # date -> earliest pickup that day, to check out in time
    for it in trip["items"]:
        if it["type"] == "transfer":
            pickups[it["start"][:10]] = min(pickups.get(it["start"][:10], "99:99"), it["start"][11:16])
    for it in trip["items"]:
        d = it["details"]
        if it["type"] == "flight":
            f = cat.get_flight(it["catalog_id"])
            stops = "direct" if f["stops"] == 0 else f"{f['stops']} stop"
            event(it["start"], "FLIGHT_DEPARTURE", it, f"Depart {f['from_airport']}: {it['name']} ({stops})",
                  cat.get_airport(f["from_airport"])["timezone"])
            event(it["end"], "FLIGHT_ARRIVAL", it, f"Land at {f['to_airport']}: {it['name']}",
                  cat.get_airport(f["to_airport"])["timezone"])
        elif it["type"] == "transfer":
            event(it["start"], "TRANSFER", it, f"{it['name']} ({d['from_point']} to {d['to_point']})", tz)
        elif it["type"] == "attraction":
            event(it["start"], "ATTRACTION", it, it["name"], tz)
        else:
            out_time = min(d["check_out_until"], pickups.get(it["end"], "99:99"))
            # straight to the hotel on arrival, before any visit: check in when you get there, dropping bags
            # if the room isn't ready yet (the hotel's early-arrival warning says so too)
            n = int(it["item_id"].split("-")[1]) - 1
            reach, pickup = reach_at[n], legs[n]["pickup"]
            in_time, title = d["check_in_from"], f"Check in: {it['name']}"
            if reach.date().isoformat() == it["start"]:
                in_time = f"{reach:%H:%M}"
                if in_time < d["check_in_from"]:
                    title += f" (drop bags, room from {d['check_in_from']})"
            elif reach.date().isoformat() > it["start"]:  # past midnight: list it right after the ride there
                in_time = max(in_time, f"{pickup:%H:%M}") if pickup.date().isoformat() == it["start"] else "23:59"
                title += f" (arriving {reach:%H:%M})"
            event(f"{it['start']}T{in_time}", "CHECK_IN", it, title, tz)
            event(f"{it['end']}T{out_time}", "CHECK_OUT", it, f"Check out: {it['name']}", tz)

    night_city = {}
    for c in trip["cities"]:
        day = date.fromisoformat(c["check_in"])
        while day.isoformat() < c["check_out"]:
            night_city[day.isoformat()] = c["city"]
            day += timedelta(1)
    change_days = {c["check_in"] for c in trip["cities"][1:]}
    first, last = min(min(events), start), max(max(events), end)
    days, day = [], date.fromisoformat(first)
    while day.isoformat() <= last:
        iso = day.isoformat()
        day_type = ("TRAVEL" if iso < start else "ARRIVAL" if iso == start else "HOME" if iso > end
                    else "RETURN" if iso == end else "CITY_CHANGE" if iso in change_days else "FULL")
        city = None if day_type in ("TRAVEL", "HOME") else trip["cities"][-1]["city"] if day_type == "RETURN" \
            else night_city[iso]
        days.append({"date": iso, "day_type": day_type, "city": city,
                     "events": sorted(events.get(iso, []), key=lambda e: (e["time"], e["kind"] == "CHECK_IN"))})
        day += timedelta(1)
    return days

