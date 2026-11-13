"""Builds the first package for a request (M2, M3, M8).

Every city plan of the country is tried. For each plan the cheapest parts that satisfy the travel
rules are picked; the result must then pass validator.validate() or it is dropped. The cheapest
package that passes is returned. When none exists, the reasons (blockers) and working nearby
requests (alternatives) are reported. Only catalog data is used.

Attractions: one on each full day, plus (while the package stays within the budget) a second one on a full
day and one on an arrival or city-change day the traveler reaches in time; none on the last day. Each day
allows for travel time between the hotel and the visits (see _plan_visits). No optional city taxis.
"""
import logging
from datetime import timedelta
from itertools import product

from app.core.timeutil import DAYS, at, first_pickup, last_pickup, parse_hhmm
from app.schemas.search import THEMES
from app.services import package, pricing, travel, validator
from app.services.travel import CHECKIN_BUFFER, CLOSE_BUFFER, DAY_END, STOP_BUFFER

log = logging.getLogger(__name__)
STAGES = ["NO_DEPARTURE_FLIGHTS", "NO_CITY_PLAN", "NO_ARRIVAL_FLIGHT", "ARRIVAL_SEATS", "NO_RETURN_FLIGHT", "RETURN_SEATS", "NO_ROOM_FITS",
          "HOTEL_SOLD_OUT", "NO_AIRPORT_TRANSFER", "ARRIVAL_TOO_LATE", "RETURN_TOO_EARLY", "NO_INTERCITY",
          "NOT_ENOUGH_ATTRACTIONS", "RULE_CHECK"]  # in build order: a later code means the plan got further
PARTS = {"FLIGHT": "flight", "SEATS": "flight", "ROOM": "hotel", "HOTEL": "hotel", "TRANSFER": "transfer",
         "LATE": "transfer", "EARLY": "transfer", "INTERCITY": "transfer", "ATTRACTIONS": "attraction"}
RULE_PARTS = {"ATTRACTION": "attraction", "TRANSFER": "transfer", "SERVICE": "transfer", "PICKUP": "transfer",
              "AIRPORT": "transfer", "HOTEL": "hotel", "ROOM": "hotel", "CITY": "hotel"}  # validator code -> part
MAX_WAIT_AT_AIRPORT = 240  # minutes after landing + 60 to wait for the first transfer
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


def airport_leg(cat, flights, hotel, A, C, arriving, objective="cheapest"):
    """Best (cost, flight, transfer, pickup) for this hotel, or a string saying why there is none.
    Best is the cheapest, or the shortest flight when the objective is "fastest" (cost breaks ties).

    Arrival: pickup at least 60 minutes after landing. Return: at the airport at least 180 minutes
    before departure, leaving the hotel on the last day. Both ends are local time of the destination.
    """
    # many city plans share the first or last hotel: work each (flights, hotel) out once per request
    memo = cat.__dict__.setdefault("_airport_legs", {})
    key = (tuple(f["flight_id"] for f in flights), hotel["hotel_id"], A, C, arriving, objective)
    if key not in memo:
        memo[key] = _airport_leg(cat, flights, hotel, A, C, arriving, objective)
    return memo[key]


def _airport_leg(cat, flights, hotel, A, C, arriving, objective):
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
                key = (f["duration_minutes"] if objective == "fastest" else 0, cost, f["flight_id"], t["transfer_id"])
                if best is None or key < best[0]:
                    best = (key, cost, f, t, pickup)
    if best:
        return best[1:]
    return "hours" if seen_transfer else "none"


def build_plan(request, plan, cat, objective="cheapest"):
    """The best selection for one city plan: (cost, selection). Raises Blocked with the reason.

    objective picks which part wins when several fit: "cheapest" (lowest price), "fastest" (shortest flights
    and city-to-city transfers) or "best_rated" (most hotel stars). Price breaks ties; every rule still applies.
    """
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
    choices = []  # per city: [(rank, room, k, chosen)], best first
    for i, (city, ci, co) in enumerate(spans):
        best, why = {}, {}
        for price, room, k in rooms[i]:
            hotel = cat.get_hotel(room["hotel_id"])
            total, chosen = price, {}
            for arriving, flights, here in ((True, arrivals, i == 0), (False, returns, i == len(spans) - 1)):
                if here:
                    leg = airport_leg(cat, flights, hotel, A, C, arriving, objective)
                    if isinstance(leg, str):
                        why.setdefault(arriving, set()).add(leg)
                        total = None
                        break
                    why.setdefault(arriving, set()).add("ok")
                    chosen[arriving] = leg
                    total += leg[0]
            if total is not None:
                rank = (-hotel["stars"] if objective == "best_rated" else 0,
                        sum(x[1]["duration_minutes"] for x in chosen.values()) if objective == "fastest" else 0,
                        total, room["room_id"])
                # best_rated keeps the cheapest hotel at every star level; the budget chooses among them below
                level = rank[0]
                if level not in best or rank < best[level][0]:
                    best[level] = (rank, room, k, chosen)
        if not best:
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
        choices.append(sorted(best.values(), key=lambda b: b[0]))

    intercity, moves = [], 0
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
                key = (t["duration_minutes"] if objective == "fastest" else 0, pricing.transfer_price(t, A, C), tid)
                if best is None or key < best[0]:
                    best = (key, t, pickup)
        if not best:
            raise Blocked("NO_INTERCITY", f"No transfer from {a} to {b} runs on {change_day}.")
        moves += best[0][1]
        intercity.append({"transfer_id": best[1]["transfer_id"], "pickup": best[2]})

    # one hotel per city: the most star-nights first (best_rated), then the cheapest. The first mix within the
    # budget wins; if none fits, the first that works (it is then dropped for being over budget, as before).
    nights = [(co - ci).days for _, ci, co in spans]
    mixes = sorted(product(*choices), key=lambda m: (sum(b[0][0] * n for b, n in zip(m, nights)),
                                                     sum(b[0][2] for b in m)))
    found, blocked = None, None
    for mix in mixes:
        stays, legs, cost = [], {}, moves
        for (rank, room, k, chosen), (_, ci, co) in zip(mix, spans):
            cost += rank[2]
            legs.update(chosen)
            stays.append({"hotel_id": room["hotel_id"], "room_id": room["room_id"], "rooms": k,
                          "check_in": ci, "check_out": co})
        try:
            days, cost = _plan_visits(request, spans, stays, legs, intercity, cat, cost)
        except Blocked as e:
            blocked = blocked or e
            continue
        found = found or (cost, stays, legs, days)
        if cost <= request["budget_inr"]:
            found = (cost, stays, legs, days)
            break
    if not found:
        raise blocked
    cost, stays, legs, days = found
    visits = [{"attraction_id": a["attraction_id"], "start": s} for plan in days.values() for a, s in plan]

    selection = {
        "arrival": {"flight_id": legs[True][1]["flight_id"], "transfer_id": legs[True][2]["transfer_id"],
                    "pickup": legs[True][3]},
        "return": {"flight_id": legs[False][1]["flight_id"], "transfer_id": legs[False][2]["transfer_id"],
                   "pickup": legs[False][3]},
        "stays": stays, "intercity": intercity, "attractions": sorted(visits, key=lambda x: x["start"]),
    }
    return cost, selection


def _plan_visits(request, spans, stays, legs, intercity, cat, cost):
    """({day: [(attraction, start)]}, cost with the visits).

    Full days get the cheapest visit that fits, then (within the budget) a second one, nearest to the
    first visit first. Arrival and city-change days then get one visit if the traveler reaches the city in
    time and the budget allows. Each day is a real day: leave the hotel, travel, visit (ending CLOSE_BUFFER
    before closing), STOP_BUFFER, travel, ... and back at the hotel by DAY_END."""
    A, C = request["adults"], len(request["child_ages"])
    kids, budget, move = C > 0, request["budget_inr"], travel.for_catalog(cat)
    price = lambda a: pricing.attraction_price(a, A, C)
    hotel = {}   # day -> hotel of that night
    leave = {}   # arrival / city-change day -> earliest time to leave the hotel
    for (city, ci, co), stay in zip(spans, stays):
        h = cat.get_hotel(stay["hotel_id"])
        for i in range((co - ci).days):
            hotel[ci + timedelta(i)] = h
    arrival = legs[True]
    leave[spans[0][1]] = arrival[3] + timedelta(minutes=arrival[2]["duration_minutes"] + CHECKIN_BUFFER)
    for (_, change_day, _), leg in zip(spans[1:], intercity):
        reach = leg["pickup"] + timedelta(minutes=cat.get_transfer(leg["transfer_id"])["duration_minutes"])
        leave[change_day] = reach + timedelta(minutes=CHECKIN_BUFFER)
    full = [(day, city) for city, ci, co in spans for day in (ci + timedelta(i) for i in range((co - ci).days))
            if day != ci]
    # every city plan of the request re-plans the same days with the same hotels: remember the answers
    memo = cat.__dict__.setdefault("_schedules", {})

    def plan(day, stops):
        key = (hotel[day]["hotel_id"], day, leave.get(day), kids, tuple(a["attraction_id"] for a in stops))
        if key not in memo:
            memo[key] = _schedule(hotel[day], stops, day, leave.get(day), move, kids)
        return memo[key]

    wanted = THEMES[request.get("theme", "mixed")]
    miss = (lambda a: a["category"] not in wanted) if wanted else (lambda a: False)  # theme first, then price
    options = {day: [a for a in cat.attractions_in(city) if plan(day, [a])] for day, city in full}
    used, days = set(), {}
    # ponytail: greedy (days with the fewest options first), not a full matching. A plan it cannot fill
    # is dropped while other plans still compete. Use bipartite matching if plans are lost this way.
    for day, city in sorted(full, key=lambda x: (len(options[x[0]]), x[0])):
        free = [a for a in options[day] if a["attraction_id"] not in used]
        if not free:
            raise Blocked("NOT_ENOUGH_ATTRACTIONS", _attraction_reason(cat, city, day, kids, used, plan))
        a = min(free, key=lambda a: (miss(a), price(a), move.minutes(hotel[day], a), a["attraction_id"]))
        used.add(a["attraction_id"])
        cost += price(a)
        days[day] = plan(day, [a])

    # arrival / city-change days first (one visit on every day before any day gets two), then second
    # visits, while the package stays within the budget
    # ponytail: greedy by travel then price; a knapsack would fit more visits into a tight budget
    extras = []
    for day, city in full:
        (first, _), = days[day]
        for a in cat.attractions_in(city):
            pair = sorted([first, a], key=lambda x: (move.minutes(hotel[day], x), x["attraction_id"]))  # nearest first
            fit = a["attraction_id"] not in used and (plan(day, pair) or plan(day, pair[::-1]))
            if fit:
                extras.append((1, miss(a), move.minutes(first, a), price(a), a["attraction_id"], day, a, fit))
    for day in leave:
        if day in hotel and day not in days:  # not the last day (no hotel that night)
            for a in cat.attractions_in(hotel[day]["city"]):
                fit = a["attraction_id"] not in used and plan(day, [a])
                if fit:
                    extras.append((0, miss(a), move.minutes(hotel[day], a), price(a), a["attraction_id"], day, a, fit))
    filled = set()
    for _, _, _, p, aid, day, a, fit in sorted(extras, key=lambda e: e[:6]):
        if day not in filled and aid not in used and cost + p <= budget:
            filled.add(day)
            used.add(aid)
            cost += p
            days[day] = fit
    return days, cost


def _attraction_reason(cat, city, day, kids, used, plan):
    """Why no attraction is left for this day: how many are closed, not for children, too tight, or used."""
    found = cat.attractions_in(city)
    if not found:
        return f"{city} has no attractions to visit on {day}."
    counts = dict.fromkeys(("closed", "child", "timing", "used"), 0)
    for a in found:
        if DAYS[day.weekday()] not in a["open_days"] or day in a["closed_dates"]:
            counts["closed"] += 1
        elif kids and not a["child_friendly"]:
            counts["child"] += 1
        elif not plan(day, [a]):
            counts["timing"] += 1
        else:
            counts["used"] += 1
    words = {"closed": f"{{}} closed on {day}", "child": "{} not child-friendly (children travel)",
             "timing": "{} cannot be visited in time that day", "used": "{} already used on another day"}
    why = ", ".join(words[k].format(n) for k, n in counts.items() if n)
    return f"{city} has no attraction left for {day}: {why}."


def _schedule(hotel, stops, day, leave, move, kids):
    """[(attraction, start)] visiting the stops in this order on `day`, or None when the day does not work.
    leave: earliest time to leave the hotel (arrival and city-change days); on a full day the first visit
    starts at VISIT_FROM at the earliest. Starts are rounded up to 5 minutes."""
    out, here, free = [], hotel, leave
    for a in stops:
        if (kids and not a["child_friendly"]) or DAYS[day.weekday()] not in a["open_days"] or day in a["closed_dates"]:
            return None
        earliest = max(at(day, VISIT_FROM), at(day, a["open_from"]))
        if free:
            earliest = max(earliest, free + timedelta(minutes=move.minutes(here, a)))
        start = at(day, "00:00") + timedelta(minutes=-(-minute_of(earliest, day) // 5) * 5)
        end = start + timedelta(minutes=a["visit_minutes"])
        if end > at(day, "00:00") + timedelta(minutes=parse_hhmm(a["open_until"]) - CLOSE_BUFFER):
            return None
        out.append((a, start))
        here, free = a, end + timedelta(minutes=travel.overrun(a) + STOP_BUFFER)
    back = out[-1][1] + timedelta(minutes=here["visit_minutes"] + travel.overrun(here) + move.minutes(here, hotel))
    return out if back <= at(day, DAY_END) else None


def minute_of(t, day):
    """Minutes from the start of `day` to t."""
    return (t - at(day, "00:00")) // timedelta(minutes=1)


# ---------- the whole request ----------

def _departure_airports(cat):
    return [d["airport"] for d in cat.destinations["departure_cities"]]


def _country_flights(request, cat):
    """Blocker when no flight at all works for the country, so the reason is one clear sentence."""
    home, country, n = request["departure_city"], request["country"], request["adults"] + len(request["child_ages"])
    if home not in _departure_airports(cat):
        return Blocked("NO_DEPARTURE_FLIGHTS", f"No flights exist from {home}.").blocker
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


def _ranked(built, request, cat, objective):
    """(trip, selection) for every built plan, best first for the objective; ties keep the plan order."""
    if objective == "cheapest":  # cheap path: only assemble what the caller reads
        for _, selection in sorted(built, key=lambda x: x[0]):
            yield package.assemble(request, selection, cat), selection
        return
    trips = [(package.assemble(request, selection, cat), selection) for _, selection in built]
    measure = {"fastest": lambda t: (package.travel_minutes(t["items"]), t["total_inr"]),
               "best_rated": lambda t: (-package.avg_stars(t["items"]), t["total_inr"])}[objective]
    yield from sorted(trips, key=lambda x: measure(x[0]))


def _valid(request, cat, limit=1, objective="cheapest"):
    """([(trip, selection)], None): up to `limit` packages that pass every rule, ignoring the budget,
    best first for the objective (cheapest by default); else ([], blockers)."""
    blocker = _country_flights(request, cat)
    if blocker:
        return [], [blocker]
    built, blocked, valid = [], [], []
    picked = set(request.get("cities", []))  # every package visits every picked city
    for plan in city_plans(request["country"], request["nights"], cat):
        if not picked <= {city for city, _ in plan}:
            continue
        try:
            built.append(build_plan(request, plan, cat, objective))
        except Blocked as e:
            blocked.append(e.blocker)
    for trip, selection in _ranked(built, request, cat, objective):
        problems = validator.validate(trip, cat)  # the gate: nothing leaves without passing every rule
        if not problems:
            valid.append((trip, selection))
            if len(valid) >= limit:
                break
            continue
        log.error("built package failed the rule check and was dropped: %s", problems)
        code = problems[0].split(":")[0]
        part = next((p for k, p in RULE_PARTS.items() if k in code), "flight")
        blocked.append({"code": "RULE_CHECK", "part": part,
                        "message": f"A package was built but failed the rule check ({problems[0]}), "
                                   "so it was not returned."})
    if valid:
        return valid, None
    if not blocked:
        blocked = [{"code": "NO_CITY_PLAN", "part": "hotel", "message": "No city plan fits the number of nights."}]
    # reasons shared by the most plans that got furthest come first
    count = {}
    for b in blocked:
        count[(b["code"], b["message"])] = count.get((b["code"], b["message"]), 0) + 1
    unique = {(b["code"], b["message"]): b for b in blocked}
    order = sorted(unique, key=lambda k: (-STAGES.index(k[0]), -count[k], k[1]))
    return [], [unique[k] for k in order[:5]]


def _cheapest(request, cat):
    """((trip, selection), None) for the cheapest package that passes every rule, ignoring the budget;
    else (None, blockers)."""
    valid, blockers = _valid(request, cat)
    return (valid[0], None) if valid else (None, blockers)


def _nearby(request, cat):
    """Requests close to this one, as (change in request-form terms, normalized request)."""
    rules = cat.destinations["rules"]
    first, last = rules["data_window"]["first_night"], rules["data_window"]["last_departure"]
    for shift in (1, -1, 2, -2, 3, -3) if request["departure_city"] in _departure_airports(cat) else ():
        start = request["start_date"] + timedelta(shift)
        end = start + timedelta(request["nights"])
        if start.isoformat() >= first and end.isoformat() <= last:
            yield {"start_date": start.isoformat()}, dict(request, start_date=start, end_date=end)
    for nights in (request["nights"] - 1, request["nights"] + 1) if request["departure_city"] in _departure_airports(cat) else ():
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
    if found and found[0]["total_inr"] <= request["budget_inr"]:
        return found
    _fail(request, cat, found, blockers)


def build_many(request, cat, limit=30):
    """[(trip, selection)]: up to `limit` packages that pass every rule and fit the budget, cheapest first
    (one per city plan). Raises NoPackage or OverBudget exactly like build_selection."""
    valid, blockers = _valid(request, cat, limit)
    fits = [f for f in valid if f[0]["total_inr"] <= request["budget_inr"]]
    if fits:
        return sorted(fits, key=lambda f: f[0]["total_inr"])
    _fail(request, cat, valid[0] if valid else None, blockers)


def build_picks(request, cat):
    """{"cheapest" | "fastest" | "best_rated": (trip, selection)}: the best package for each measure that fits
    the budget (G4). A measure with no package inside the budget is left out; a tie keeps the first."""
    picks = {}
    for objective in ("cheapest", "fastest", "best_rated"):
        valid, _ = _valid(request, cat, limit=10_000, objective=objective)
        fit = next((f for f in valid if f[0]["total_inr"] <= request["budget_inr"]), None)
        if fit:
            picks[objective] = fit
    return picks


def _fail(request, cat, found, blockers):
    """Always raises: OverBudget when `found` (the cheapest package) exceeds the budget, else NoPackage."""
    budget = request["budget_inr"]
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
            "NO_DEPARTURE_FLIGHTS": "Flights leave from "
            + ", ".join(f"{d['city']} ({d['airport']})" for d in cat.destinations["departure_cities"])
            + ". Choose one of them as the departure city.",
            "NO_ROOM_FITS": "Add an adult or travel with fewer children: each room needs an adult.",
        }.get(blockers[0]["code"], "Nearby dates and other departure cities do not work either. "
                                    "Try a different week or the other country.")
    raise NoPackage(blockers, suggestion, alternatives)
