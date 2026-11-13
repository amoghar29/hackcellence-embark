"""Builds the first package for a request (M2, M3, M8).

Every city plan of the country is tried. For each plan the cheapest parts that satisfy the travel
rules are picked; the result must then pass validator.validate() or it is dropped. The cheapest
package that passes is returned. When none exists, the reasons (blockers) and working nearby
requests (alternatives) are reported. Only catalog data is used.

Deliberately simple: one attraction on each full day and none on the arrival, city-change and last
days (the rules ask for no more), and no optional city taxis.
"""
import logging
from datetime import timedelta

from app.core.timeutil import DAYS, at, first_pickup, last_pickup, parse_hhmm
from app.services import package, pricing, validator

log = logging.getLogger(__name__)
STAGES = ["NO_CITY_PLAN", "NO_ARRIVAL_FLIGHT", "ARRIVAL_SEATS", "NO_RETURN_FLIGHT", "RETURN_SEATS", "NO_ROOM_FITS",
          "HOTEL_SOLD_OUT", "NO_AIRPORT_TRANSFER", "ARRIVAL_TOO_LATE", "RETURN_TOO_EARLY", "NO_INTERCITY",
          "NOT_ENOUGH_ATTRACTIONS", "RULE_CHECK"]  # in build order: a later code means the plan got further
PARTS = {"FLIGHT": "flight", "SEATS": "flight", "ROOM": "hotel", "HOTEL": "hotel", "TRANSFER": "transfer",
         "LATE": "transfer", "EARLY": "transfer", "INTERCITY": "transfer", "ATTRACTIONS": "attraction"}
MAX_WAIT_AT_AIRPORT = 240   # minutes after landing + 60 to wait for the first transfer
INTERCITY_FROM = "09:00"    # earliest departure on a city-change day
VISIT_FROM = "10:00"        # a visit starts here, or at opening time if that is later


class NoPackage(Exception):
    def __init__(self, blockers, suggestion, alternatives):
        super().__init__(blockers[0]["message"])
        self.blockers, self.suggestion, self.alternatives = blockers, suggestion, alternatives
        self.reasons = [b["message"] for b in blockers]


class OverBudget(Exception):
    def __init__(self, budget_inr, cheapest_total_inr, suggestion, alternatives):
        super().__init__(f"No package fits a budget of {inr(budget_inr)}.")
        self.budget_inr, self.cheapest_total_inr = budget_inr, cheapest_total_inr
        self.suggestion, self.alternatives = suggestion, alternatives


class Blocked(Exception):
    def __init__(self, code, message):
        self.blocker = {"code": code, "part": next(p for k, p in PARTS.items() if k in code), "message": message}


def inr(n):
    """350000 -> '₹3,50,000' (Indian grouping)."""
    s = str(n)
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(([head] if head else []) + groups + [tail])


def people(adults, children):
    a = f"{adults} adult{'s' if adults != 1 else ''}"
    return a if not children else f"{a} and {children} child{'ren' if children != 1 else ''}"


# ---------- city plans ----------

def city_plans(country, nights, cat):
    """Every ordered list of distinct linked cities, with every split of the nights (2 or more per city)."""
    c = cat.country(country)
    links = {(link["from_city"], link["to_city"]) for link in c["links"]}
    least = cat.destinations["rules"]["min_nights_per_city"]

    def routes(route):
        yield route
        for city in (x["name"] for x in c["cities"]):
            if city not in route and (route[-1], city) in links:
                yield from routes(route + [city])

    def splits(n, parts):
        if parts == 1:
            yield [n]
            return
        for first in range(least, n - least * (parts - 1) + 1):
            for rest in splits(n - first, parts - 1):
                yield [first] + rest

    return [list(zip(route, split))
            for start in c["cities"] for route in routes([start["name"]])
            if len(route) * least <= nights
            for split in splits(nights, len(route))]


# ---------- one plan ----------

def matching_flights(cat, home, city, day, n, arriving):
    """Flights between the home airport and an airport serving the city on that local day, with n seats."""
    found = cat.flights(home, [city], day, arriving)
    verb = f"from {home} lands in {city}" if arriving else f"from {city} to {home} leaves"
    if not found:
        raise Blocked("NO_ARRIVAL_FLIGHT" if arriving else "NO_RETURN_FLIGHT", f"No flight {verb} on {day}.")
    seated = [f for f in found if f["seats_left"] >= n]
    if not seated:
        route = f"from {home} to {city}" if arriving else f"from {city} to {home}"
        raise Blocked("ARRIVAL_SEATS" if arriving else "RETURN_SEATS",
                       f"Flights {route} on {day} have at most {max(f['seats_left'] for f in found)} free seats; "
                       f"you need {n}.")
    return seated


def _rooms(cat, city, check_in, check_out, A, C):
    """[(price, room, k)] for room types in the city that fit the travelers and are free every night."""
    nights = [check_in + timedelta(i) for i in range((check_out - check_in).days)]
    fits = [(r, pricing.rooms_needed(r, A, C)) for r in cat.rooms_in(city)]
    fits = [(r, k) for r, k in fits if k]
    if not fits:
        raise Blocked("NO_ROOM_FITS", f"No room type in {city} fits {people(A, C)} (each room needs an adult).")
    free = [(pricing.hotel_price(r, k, len(nights)), r, k) for r, k in fits
            if all(cat.rooms_left(r["room_id"], n) >= k for n in nights)]
    if not free:
        full = [str(n) for n in nights if all(cat.rooms_left(r["room_id"], n) < k for r, k in fits)]
        raise Blocked("HOTEL_SOLD_OUT", f"No hotel in {city} has rooms for {people(A, C)} on every night from "
                       f"{check_in} to {check_out}" + (f" (sold out: {', '.join(full)})." if full else "."))
    return free


def airport_leg(cat, flights, hotel, A, C, arriving):
    """Cheapest (cost, flight, transfer, pickup) for this hotel, or a string saying why there is none.

    Arrival: pickup at least 60 minutes after landing. Return: at the airport at least 180 minutes
    before departure, leaving the hotel on the last day. Both ends are local time of the destination.
    """
    best, seen_transfer = None, False
    for f in flights:
        airport = f["to_airport"] if arriving else f["from_airport"]
        for t in cat.airport_transfers(airport, hotel["city"], hotel["area"]):
            seen_transfer = True
            if arriving:
                pickup = first_pickup(t, f["arrival_local"] + timedelta(minutes=60), MAX_WAIT_AT_AIRPORT)
            else:
                # ponytail: the pickup must be on the last day; a flight around 01:00-03:00 that needs leaving
                # the hotel the evening before is skipped. Allow the previous evening if such requests matter.
                pickup = last_pickup(t, f["departure_local"] - timedelta(minutes=180 + t["duration_minutes"]))
                if pickup and pickup.date() != f["departure_local"].date():
                    pickup = None
            if pickup:
                cost = pricing.flight_price(f, A + C) + pricing.transfer_price(t, A, C)
                key = (cost, f["flight_id"], t["transfer_id"])
                if best is None or key < best[0]:
                    best = (key, f, t, pickup)
    if best:
        return best[0][0], best[1], best[2], best[3]
    return "hours" if seen_transfer else "none"


def _plan(request, plan, cat):
    """The cheapest selection for one city plan: (cost, selection). Raises Blocked with the reason."""
    A, C = request["adults"], len(request["child_ages"])
    N, home, start, end = A + C, request["departure_city"], request["start_date"], request["end_date"]
    first_city, last_city = plan[0][0], plan[-1][0]

    arrivals = matching_flights(cat, home, first_city, start, N, arriving=True)
    returns = matching_flights(cat, home, last_city, end, N, arriving=False)

    spans, day = [], start
    for city, nights in plan:
        spans.append((city, day, day + timedelta(nights)))
        day += timedelta(nights)
    rooms = [_rooms(cat, city, ci, co, A, C) for city, ci, co in spans]

    # the first and last hotel decide the airport transfers (by area), so choose them together with the flights
    stays, legs, cost = [], {}, 0
    for i, (city, ci, co) in enumerate(spans):
        best, why = None, {}
        for price, room, k in rooms[i]:
            hotel = cat.get_hotel(room["hotel_id"])
            total, chosen = price, {}
            for arriving, flights, here in ((True, arrivals, i == 0), (False, returns, i == len(spans) - 1)):
                if here:
                    leg = airport_leg(cat, flights, hotel, A, C, arriving)
                    if isinstance(leg, str):
                        why.setdefault(arriving, set()).add(leg)
                        total = None
                        break
                    why.setdefault(arriving, set()).add("ok")
                    chosen[arriving] = leg
                    total += leg[0]
            if total is not None and (best is None or (total, room["room_id"]) < best[0]):
                best = ((total, room["room_id"]), room, k, chosen)
        if best is None:
            arriving = "ok" not in why.get(True, {"ok"})  # which side never worked for any hotel
            flights = arrivals if arriving else returns
            reasons = why[arriving]
            if "hours" not in reasons:
                airports = sorted({f["to_airport" if arriving else "from_airport"] for f in flights})
                raise Blocked("NO_AIRPORT_TRANSFER",
                               f"No transfer from {' or '.join(airports)} serves the available hotels in {city}.")
            if arriving:
                latest = max(f["arrival_local"] for f in flights)
                raise Blocked("ARRIVAL_TOO_LATE", f"Flights from {home} land in {city} by {latest:%H:%M} on {start}; "
                               "no airport transfer is in service 60 minutes after landing.")
            earliest = min(f["departure_local"] for f in flights)
            raise Blocked("RETURN_TOO_EARLY", f"Flights from {city} to {home} on {end} leave from {earliest:%H:%M}; "
                           "no transfer on that day reaches the airport 180 minutes before departure.")
        (total, _), room, k, chosen = best
        cost += total
        legs.update(chosen)
        stays.append({"hotel_id": room["hotel_id"], "room_id": room["room_id"], "rooms": k,
                      "check_in": ci, "check_out": co})

    intercity = []
    for (a, _, change_day), (b, _, _) in zip(spans, spans[1:]):
        link = next(x for x in cat.country(request["country"])["links"] if (x["from_city"], x["to_city"]) == (a, b))
        best = None
        for tid in link["transfer_ids"]:
            t = cat.get_transfer(tid)
            if not t:
                continue
            earliest = at(change_day, INTERCITY_FROM)
            pickup = first_pickup(t, earliest, 24 * 60 - 1 - parse_hhmm(INTERCITY_FROM))
            if pickup and pickup.date() == change_day:
                key = (pricing.transfer_price(t, A, C), tid)
                if best is None or key < best[0]:
                    best = (key, t, pickup)
        if not best:
            raise Blocked("NO_INTERCITY", f"No transfer from {a} to {b} runs on {change_day}.")
        cost += best[0][0]
        intercity.append({"transfer_id": best[1]["transfer_id"], "pickup": best[2]})

    # full days only: not the arrival day, not a city-change day, not the last day
    full_days = [(day, city) for city, ci, co in spans for day in (ci + timedelta(i) for i in range((co - ci).days))
                 if day != ci]
    options = {day: _open_attractions(cat, city, day) for day, city in full_days}
    used, visits = set(), []
    # ponytail: greedy (days with the fewest options first), not a full matching. A plan it cannot fill
    # is dropped while other plans still compete. Use bipartite matching if plans are lost this way.
    for day, city in sorted(full_days, key=lambda x: (len(options[x[0]]), x[0])):
        free = [(pricing.attraction_price(a, A, C), a["attraction_id"], s) for a, s in options[day]
                if a["attraction_id"] not in used]
        if not free:
            raise Blocked("NOT_ENOUGH_ATTRACTIONS", f"{city} has no open attraction left for {day}.")
        price, aid, visit_start = min(free)
        used.add(aid)
        cost += price
        visits.append({"attraction_id": aid, "start": visit_start})

    selection = {
        "arrival": {"flight_id": legs[True][1]["flight_id"], "transfer_id": legs[True][2]["transfer_id"],
                    "pickup": legs[True][3]},
        "return": {"flight_id": legs[False][1]["flight_id"], "transfer_id": legs[False][2]["transfer_id"],
                   "pickup": legs[False][3]},
        "stays": stays, "intercity": intercity, "attractions": sorted(visits, key=lambda x: x["start"]),
    }
    return cost, selection


def _open_attractions(cat, city, day):
    """[(attraction, visit start)] for attractions in the city that are open that day and fit a whole visit."""
    out = []
    for a in cat.attractions_in(city):
        if DAYS[day.weekday()] not in a["open_days"] or day in a["closed_dates"]:
            continue
        opens, closes = parse_hhmm(a["open_from"]), parse_hhmm(a["open_until"])
        begin = max(opens, parse_hhmm(VISIT_FROM))
        if begin + a["visit_minutes"] > closes:
            begin = opens
        if begin + a["visit_minutes"] <= closes:
            out.append((a, at(day, "00:00") + timedelta(minutes=begin)))
    return out


# ---------- the whole request ----------

def _country_flights(request, cat):
    """Blocker when no flight at all works for the country, so the reason is one clear sentence."""
    home, country, n = request["departure_city"], request["country"], request["adults"] + len(request["child_ages"])
    cities = [c["name"] for c in cat.country(country)["cities"]]
    for arriving, day in ((True, request["start_date"]), (False, request["end_date"])):
        found = cat.flights(home, cities, day, arriving)
        if arriving:
            none = f"No flight from {home} lands in {country} on {day}."
            route = f"from {home} to {country}"
        else:
            none = f"No flight from {country} to {home} leaves on {day}."
            route = f"from {country} to {home}"
        if not found:
            return Blocked("NO_ARRIVAL_FLIGHT" if arriving else "NO_RETURN_FLIGHT", none).blocker
        seats = max(f["seats_left"] for f in found)
        if seats < n:
            return Blocked("ARRIVAL_SEATS" if arriving else "RETURN_SEATS",
                            f"Flights {route} on {day} have at most {seats} free seats; you need {n}.").blocker
    return None


def _cheapest(request, cat):
    """((trip, selection), None) for the cheapest package that passes every rule, ignoring the budget;
    else (None, blockers)."""
    blocker = _country_flights(request, cat)
    if blocker:
        return None, [blocker]
    built, blocked = [], []
    for plan in city_plans(request["country"], request["nights"], cat):
        try:
            built.append(_plan(request, plan, cat))
        except Blocked as e:
            blocked.append(e.blocker)
    for _, selection in sorted(built, key=lambda x: x[0]):  # stable: ties keep the plan order
        trip = package.assemble(None, request, selection, cat)
        problems = validator.validate(trip, cat)  # the gate: nothing leaves without passing every rule
        if not problems:
            return (trip, selection), None
        log.error("built package failed the rule check and was dropped: %s", problems)
        blocked.append({"code": "RULE_CHECK", "part": "flight",
                        "message": "A package was built but failed the rule check, so it was not returned."})
    if not blocked:
        blocked = [{"code": "NO_CITY_PLAN", "part": "hotel", "message": "No city plan fits the number of nights."}]
    # reasons shared by the most plans that got furthest come first
    count = {}
    for b in blocked:
        count[(b["code"], b["message"])] = count.get((b["code"], b["message"]), 0) + 1
    unique = {(b["code"], b["message"]): b for b in blocked}
    order = sorted(unique, key=lambda k: (-STAGES.index(k[0]), -count[k], k[1]))
    return None, [unique[k] for k in order[:5]]


def _nearby(request, cat):
    """Requests close to this one, as (change in request-form terms, normalized request)."""
    rules = cat.destinations["rules"]
    first, last = rules["data_window"]["first_night"], rules["data_window"]["last_departure"]
    for shift in (1, -1, 2, -2, 3, -3):
        start = request["start_date"] + timedelta(shift)
        end = start + timedelta(request["nights"])
        if start.isoformat() >= first and end.isoformat() <= last:
            yield {"start_date": start.isoformat()}, dict(request, start_date=start, end_date=end)
    for nights in (request["nights"] - 1, request["nights"] + 1):
        end = request["start_date"] + timedelta(nights)
        if rules["min_nights"] <= nights <= rules["max_nights"] and end.isoformat() <= last:
            yield {"nights": nights}, dict(request, nights=nights, end_date=end)
    for d in cat.destinations["departure_cities"]:
        if d["airport"] != request["departure_city"]:
            yield {"departure_city": d["airport"]}, dict(request, departure_city=d["airport"])


def _phrase(change, cat):
    if "start_date" in change:
        return f"start on {change['start_date']}"
    if "nights" in change:
        return f"stay {change['nights']} nights"
    return f"fly from {cat.home_city(change['departure_city'])}"


def build(request, cat):
    """The cheapest package that passes every rule and fits the budget. Raises NoPackage or OverBudget."""
    return build_selection(request, cat)[0]


def build_selection(request, cat):
    """build(), plus the selection behind the package (what the database stores)."""
    found, blockers = _cheapest(request, cat)
    budget = request["budget_inr"]
    if found and found[0]["total_inr"] <= budget:
        return found

    if found:  # packages exist, none fits the budget (M8)
        cheapest = found[0]["total_inr"]
        alternatives = [{"change": {"budget_inr": cheapest}, "total_inr": cheapest}]
        suggestion = f"Raise the budget to {inr(cheapest)}"
        for nights in range(request["nights"] - 1, cat.destinations["rules"]["min_nights"] - 1, -1):
            shorter, _ = _cheapest(dict(request, nights=nights,
                                        end_date=request["start_date"] + timedelta(nights)), cat)
            if shorter and shorter[0]["total_inr"] <= budget:
                alternatives.append({"change": {"nights": nights}, "total_inr": shorter[0]["total_inr"]})
                suggestion += f", or take {nights} nights ({inr(shorter[0]['total_inr'])})"
                break
        raise OverBudget(budget, cheapest, suggestion + ".", alternatives)

    # ponytail: brute force, up to 11 more builds; cache per request if a failed search ever feels slow
    alternatives = []
    for change, other in _nearby(request, cat):
        near, _ = _cheapest(other, cat)
        if near and near[0]["total_inr"] <= budget:
            alternatives.append({"change": change, "total_inr": near[0]["total_inr"]})
        if len(alternatives) == 3:
            break
    if alternatives:
        suggestion = "A package is possible if you " + ", or ".join(_phrase(a["change"], cat) for a in alternatives) + "."
    else:
        suggestion = {
            "ARRIVAL_SEATS": "No flight on nearby dates has enough free seats. Travel in a smaller group.",
            "RETURN_SEATS": "No flight on nearby dates has enough free seats. Travel in a smaller group.",
            "NO_ROOM_FITS": "Add an adult or travel with fewer children: each room needs an adult.",
        }.get(blockers[0]["code"], "Nearby dates and other departure cities do not work either. "
                                    "Try a different week or the other country.")
    raise NoPackage(blockers, suggestion, alternatives)
