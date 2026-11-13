"""Changing a package (M6, G1, G2, G3): one change at a time, on the stored selection.

A change is applied to a copy, the airport transfer is re-picked when the hotel or flight it depends on
changes, and the whole package is checked again by the validator. A refused change changes nothing.
"""
import copy
from datetime import datetime, timedelta

from app.core.timeutil import DAYS, parse_hhmm
from app.services import builder, package, pricing, travel, validator
from app.services.package import _reach_times
from app.services.travel import CHECKIN_BUFFER, CLOSE_BUFFER


class Refused(Exception):
    def __init__(self, reasons, blockers=()):
        super().__init__(reasons[0])
        self.reasons, self.blockers = list(reasons), list(blockers)


def _refuse(code, message):
    return Refused([message], [{"code": code, "part": builder.Blocked(code, message).blocker["part"],
                                "message": message}])


def _travelers(request):
    return request["adults"], len(request["child_ages"])


def _stay_city(cat, stay):
    return cat.get_hotel(stay["hotel_id"])["city"]


def _repick_airport_leg(request, selection, cat, arriving):
    """Keep the flight, choose the transfer again for the (new) hotel or flight time."""
    side = "arrival" if arriving else "return"
    A, C = _travelers(request)
    flight = cat.get_flight(selection[side]["flight_id"])
    hotel = cat.get_hotel(selection["stays"][0 if arriving else -1]["hotel_id"])
    leg = builder.airport_leg(cat, [flight], hotel, A, C, arriving)
    if isinstance(leg, str):
        airport = flight["to_airport" if arriving else "from_airport"]
        if leg == "none":
            raise _refuse("NO_AIRPORT_TRANSFER", f"No transfer links {airport} and {hotel['name']} ({hotel['area']}).")
        if arriving:
            raise _refuse("ARRIVAL_TOO_LATE", f"{flight['flight_number']} lands at {flight['arrival_local']:%H:%M}; "
                          f"no transfer to {hotel['name']} is in service 60 minutes after landing.")
        raise _refuse("RETURN_TOO_EARLY", f"{flight['flight_number']} leaves at {flight['departure_local']:%H:%M}; no "
                      f"transfer from {hotel['name']} reaches the airport 180 minutes before, on the last day.")
    selection[side].update(transfer_id=leg[2]["transfer_id"], pickup=leg[3])


def _nights(stay):
    return [stay["check_in"] + timedelta(i) for i in range((stay["check_out"] - stay["check_in"]).days)]


def _room_choice(request, stay, hotel, room, cat):
    """Rooms needed for this room type on the stay's nights. Raises Refused."""
    A, C = _travelers(request)
    k = pricing.rooms_needed(room, A, C)
    if not k:
        raise _refuse("NO_ROOM_FITS", f"{room['name']} at {hotel['name']} does not fit {builder.people(A, C)} "
                                      "(each room needs an adult).")
    full = [str(n) for n in _nights(stay) if cat.rooms_left(room["room_id"], n) < k]
    if full:
        raise _refuse("HOTEL_SOLD_OUT", f"{hotel['name']} does not have {k} x {room['name']} free on "
                                        f"{', '.join(full)}.")
    return k


def _check_plan(request, plan, cat):
    """[(city, nights)] for a valid plan of this request's country, else Refused with the reason."""
    try:
        plan = [(stop["city"], stop["nights"]) for stop in plan]
    except (TypeError, KeyError):
        raise Refused(['Send the plan as a list like [{"city": "Tokyo", "nights": 3}, ...].'])
    least = cat.destinations["rules"]["min_nights_per_city"]
    if sum(n for _, n in plan) != request["nights"]:
        raise Refused([f"The plan has {sum(n for _, n in plan)} nights; the trip has {request['nights']}."])
    short = next((c for c, n in plan if n < least), None)
    if short:
        raise Refused([f"{short} needs at least {least} nights."])
    if plan not in builder.city_plans(request["country"], request["nights"], cat):
        raise Refused([f"{' to '.join(c for c, _ in plan)} is not a route of cities in {request['country']} "
                       "(each city once, and each hop must be a listed link)."])
    return plan


def _drop_missed_visits(request, sel, cat):
    """G1: a later landing or another hotel moves the airport transfer; visits on the arrival day that would now
    start before the traveler reaches the city are removed (notices() reports them)."""
    leg = sel["arrival"]
    reach = leg["pickup"] + timedelta(minutes=cat.get_transfer(leg["transfer_id"])["duration_minutes"])
    sel["attractions"] = [v for v in sel["attractions"]
                          if not (v["start"].date() == request["start_date"] and v["start"] < reach)]


def _check_travel_day_visit(sel, a, start, cat):
    """Arrival and city-change days: one visit at most, starting after the traveler has reached the city,
    checked in (CHECKIN_BUFFER) and travelled from the hotel, and ending CLOSE_BUFFER before closing."""
    day = start.date()
    stays = sel["stays"]
    reach = dict(zip([s["check_in"] for s in stays], _reach_times(sel, cat)))
    if day not in reach:
        return
    if any(v["start"].date() == day for v in sel["attractions"]):
        raise Refused([f"{day} is a travel day: only one experience fits."])
    hotel = cat.get_hotel(next(s["hotel_id"] for s in stays if s["check_in"] <= day < s["check_out"]))
    earliest = reach[day] + timedelta(minutes=CHECKIN_BUFFER + travel.for_catalog(cat).minutes(hotel, a))
    if start < earliest:
        raise Refused([f"{a['name']} can start at {earliest:%H:%M} at the earliest on {day}: you reach the city at "
                       f"{reach[day]:%H:%M}, then check in and travel there."])
    closes = datetime.combine(day, datetime.min.time()) + timedelta(minutes=parse_hhmm(a["open_until"]) - CLOSE_BUFFER)
    if start + timedelta(minutes=a["visit_minutes"]) > closes:
        raise Refused([f"{a['name']} must end by {closes:%H:%M} ({CLOSE_BUFFER} min before it closes)."])


def notices(request, before, after, change, cat):
    """What the traveler should be told about a change that was applied: [{"level", "message"}]."""
    out = []
    if change["action"] == "change_city_plan":
        out.append({"level": "INFO", "message": "The package was built again for the new cities, so the "
                                               "experiences were chosen again."})
    kept = {v["attraction_id"] for v in after["attractions"]}
    if change["action"] in ("change_hotel", "change_flight"):
        leg = after["arrival"]
        reach = leg["pickup"] + timedelta(minutes=cat.get_transfer(leg["transfer_id"])["duration_minutes"])
        for v in before["attractions"]:
            if v["attraction_id"] not in kept:
                out.append({"level": "FIXED", "message": f"Removed {cat.get_attraction(v['attraction_id'])['name']}: it "
                            f"would start at {v['start']:%H:%M}, before you reach {_stay_city(cat, after['stays'][0])} "
                            f"at {reach:%H:%M}."})
    return out


def apply(request, selection, change, cat):
    """Returns the new selection. Raises Refused with the reasons; the given selection is not touched."""
    if not isinstance(change, dict):
        raise Refused(["Send one change as a JSON object with an action."])
    sel = copy.deepcopy(selection)
    action = change.get("action")
    A, C = _travelers(request)

    if action == "change_hotel":
        i = next((n for n, s in enumerate(sel["stays"]) if _stay_city(cat, s) == change.get("city")), None)
        hotel, room = cat.get_hotel(change.get("hotel_id")), cat.get_room(change.get("room_id"))
        if i is None:
            raise Refused([f"{change.get('city')} is not a city of this package."])
        if not hotel or not room or room["hotel_id"] != hotel["hotel_id"] or hotel["city"] != change["city"]:
            raise Refused([f"That hotel and room type are not available in {change['city']}."])
        sel["stays"][i].update(hotel_id=hotel["hotel_id"], room_id=room["room_id"],
                               rooms=_room_choice(request, sel["stays"][i], hotel, room, cat))
        if i == 0:
            _repick_airport_leg(request, sel, cat, arriving=True)  # another area can need another transfer
        if i == len(sel["stays"]) - 1:
            _repick_airport_leg(request, sel, cat, arriving=False)

    elif action == "change_flight":
        side = {"flight-arrival": "arrival", "flight-return": "return"}.get(change.get("item_id"))
        f = cat.get_flight(change.get("flight_id"))
        if not side or not f:
            raise Refused(["Choose one of the package's flights and a flight from the catalog."])
        arriving = side == "arrival"
        home, day = request["departure_city"], request["start_date" if arriving else "end_date"]
        city = _stay_city(cat, sel["stays"][0 if arriving else -1])
        if arriving and (f["from_airport"] != home or f["arrival_local"].date() != day or not cat.serves(f["to_airport"], city)):
            raise Refused([f"The arrival flight must fly from {home} and land on {day} at an airport that serves {city}."])
        if not arriving and (f["to_airport"] != home or f["departure_local"].date() != day
                             or not cat.serves(f["from_airport"], city)):
            raise Refused([f"The return flight must leave on {day} from an airport that serves {city} and fly to {home}."])
        if f["seats_left"] < A + C:
            raise _refuse("ARRIVAL_SEATS" if arriving else "RETURN_SEATS",
                          f"{f['flight_number']} has {f['seats_left']} free seats; you need {A + C}.")
        sel[side]["flight_id"] = f["flight_id"]
        _repick_airport_leg(request, sel, cat, arriving)  # the new landing or departure time moves the transfer

    elif action == "add_attraction":
        a = cat.get_attraction(change.get("attraction_id"))
        try:
            start = datetime.fromisoformat(change.get("start"))
        except (TypeError, ValueError):
            start = None
        if not a or not start:
            raise Refused(["Choose an attraction from the catalog and a start time (YYYY-MM-DDTHH:MM)."])
        _check_travel_day_visit(sel, a, start, cat)
        sel["attractions"].append({"attraction_id": a["attraction_id"], "start": start})
        sel["attractions"].sort(key=lambda v: v["start"])

    elif action == "change_city_plan":
        plan = _check_plan(request, change.get("plan"), cat)
        try:
            sel = builder.build_plan(request, plan, cat)[1]  # flights, hotels, transfers and visits are chosen again
        except builder.Blocked as e:
            raise Refused([e.blocker["message"]], [e.blocker])

    elif action == "remove_attraction":
        aid = (change.get("item_id") or "").removeprefix("attraction-")
        if aid not in [v["attraction_id"] for v in sel["attractions"]]:
            raise Refused(["That attraction is not in the package."])
        sel["attractions"] = [v for v in sel["attractions"] if v["attraction_id"] != aid]

    else:
        raise Refused(["Unknown action. Use change_hotel, change_flight, change_city_plan, add_attraction "
                       "or remove_attraction."])

    if action in ("change_hotel", "change_flight"):
        _drop_missed_visits(request, sel, cat)

    # the whole package is checked again; "1-2 attractions per full day" applies to the first package only
    problems = validator.validate(package.assemble(request, sel, cat), cat, first_package=False)
    if problems:
        raise Refused([p.split(": ", 1)[1] for p in problems])
    return sel


# ---------- options, each with the price difference against the current choice (G2) ----------

def hotel_options(request, selection, city, cat):
    stay = next((s for s in selection["stays"] if _stay_city(cat, s) == city), None)
    if not stay:
        return None
    current = pricing.hotel_price(cat.get_room(stay["room_id"]), stay["rooms"], len(_nights(stay)))
    out = []
    for room in cat.rooms_in(city):
        hotel = cat.get_hotel(room["hotel_id"])
        if room["room_id"] == stay["room_id"]:
            continue
        try:
            k = _room_choice(request, stay, hotel, room, cat)
        except Refused:
            continue
        price = pricing.hotel_price(room, k, len(_nights(stay)))
        out.append({"hotel_id": hotel["hotel_id"], "room_id": room["room_id"], "name": hotel["name"],
                    "area": hotel["area"], "stars": hotel["stars"], "rating": hotel["rating"],
                    "room_type": room["room_type"], "rooms": k, "price_inr": price,
                    "price_diff_inr": price - current, "image": "/" + hotel["image"]})
    return sorted(out, key=lambda o: (o["price_inr"], o["room_id"]))


def flight_options(request, selection, direction, cat):
    arriving = direction == "ARRIVAL"
    side = "arrival" if arriving else "return"
    A, C = _travelers(request)
    city = _stay_city(cat, selection["stays"][0 if arriving else -1])
    try:
        flights = builder.matching_flights(cat, request["departure_city"], city,
                                   request["start_date" if arriving else "end_date"], A + C, arriving)
    except builder.Blocked:
        return []
    current = pricing.flight_price(cat.get_flight(selection[side]["flight_id"]), A + C)
    return sorted(({"flight_id": f["flight_id"], "flight_number": f["flight_number"], "airline": f["airline"],
                    "from_airport": f["from_airport"], "to_airport": f["to_airport"],
                    "departure": f["departure_local"].strftime("%Y-%m-%dT%H:%M"),
                    "arrival": f["arrival_local"].strftime("%Y-%m-%dT%H:%M"), "stops": f["stops"],
                    "duration_minutes": f["duration_minutes"], "price_inr": pricing.flight_price(f, A + C),
                    "price_diff_inr": pricing.flight_price(f, A + C) - current}
                   for f in flights if f["flight_id"] != selection[side]["flight_id"]),
                  key=lambda o: (o["price_inr"], o["flight_id"]))


def attraction_options(request, selection, day, cat):
    """Attractions that can still be added on that day, each at the first start time the rules allow."""
    A, C = _travelers(request)
    if not request["start_date"] <= day <= request["end_date"]:
        return []  # outside the trip no start time can pass; skip the slow search
    used = {v["attraction_id"] for v in selection["attractions"]}
    warned = {aid for aid, leg in package.day_legs(selection, cat).items() if leg["warnings"]}
    out = []
    for a in cat.list_attractions():
        if a["attraction_id"] in used or DAYS[day.weekday()] not in a["open_days"]:
            continue
        minute, last = parse_hhmm(a["open_from"]), parse_hhmm(a["open_until"]) - a["visit_minutes"]
        while minute <= last:  # ponytail: tries every 15 minutes through the validator; fine for 56 attractions
            start = datetime.combine(day, datetime.min.time()) + timedelta(minutes=minute)
            try:
                sel = apply(request, selection, {"action": "add_attraction", "attraction_id": a["attraction_id"],
                                                 "start": start.isoformat()}, cat)
            except Refused:
                minute += 15
                continue
            # only suggest a time that leaves room to travel to it and on to the next visit (no new warning)
            if any(leg["warnings"] and aid not in warned for aid, leg in package.day_legs(sel, cat).items()):
                minute += 15
                continue
            out.append({"attraction_id": a["attraction_id"], "name": a["name"], "category": a["category"],
                        "start": start.strftime("%Y-%m-%dT%H:%M"),
                        "end": (start + timedelta(minutes=a["visit_minutes"])).strftime("%Y-%m-%dT%H:%M"),
                        "price_inr": pricing.attraction_price(a, A, C), "image": "/" + a["image"],
                        "child_friendly": a["child_friendly"]})
            break
    return sorted(out, key=lambda o: (o["start"], o["attraction_id"]))


def city_plan_options(request, selection, current_total, cat, limit=30):
    """Every other way to split the trip over cities, each built the cheapest way, with the price difference (G3, G2)."""
    here = [(_stay_city(cat, s), len(_nights(s))) for s in selection["stays"]]
    out = []
    # ponytail: builds every plan on each call (a few dozen); cache per request if long trips feel slow
    for plan in builder.city_plans(request["country"], request["nights"], cat):
        try:
            _, sel = builder.build_plan(request, plan, cat)
        except builder.Blocked:
            continue
        is_current = plan == here
        total = current_total if is_current else package.assemble(request, sel, cat)["total_inr"]
        out.append({"plan": [{"city": c, "nights": n} for c, n in plan], "total_inr": total,
                    "price_diff_inr": total - current_total, "fits_budget": total <= request["budget_inr"],
                    "is_current": is_current})
    out.sort(key=lambda o: (o["total_inr"], [s["city"] for s in o["plan"]]))
    top = out[:limit]
    return top if any(o["is_current"] for o in top) else top + [o for o in out[limit:] if o["is_current"]]
