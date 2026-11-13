"""Travel time between two catalog places (hotels, attractions, airports: anything with lat/lng).

Search reads the travel_times cache and estimates every pair that is not in it, so it is fast, works
offline and gives the same plan every time. Only the warm-up command calls Google, once:

    uv run python -m app.services.travel --warm      (key: GOOGLE_MAP_API in the repo's .env, Routes API enabled)
"""
import argparse
import json
import logging
import math
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

ROAD_FACTOR = 1.4       # roads are longer than the straight line
CITY_KMH = 20           # average door-to-door speed in a city (taxi or train, with walking)
OVERHEAD_MINUTES = 10   # getting out, waiting, walking to the entrance
# a day you can actually do (used by the builder to plan and by the package to warn)
DAY_END = "20:00"       # back at the hotel by then
CLOSE_BUFFER = 30       # a visit ends at least this long before the place closes
STOP_BUFFER = 15        # minutes after a visit before moving on (exit, tickets, a coffee)
CHECKIN_BUFFER = 30     # minutes at the hotel after reaching the city, before the first visit
OVERRUN = 0.15          # a visit can run this much longer: kept free after it, before STOP_BUFFER and travel


def overrun(a):
    """Minutes kept free after a visit in case it runs long (OVERRUN of its visit time, rounded up)."""
    return math.ceil(a["visit_minutes"] * OVERRUN)
MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"  # Routes API
BATCH = 25              # 25 x 25 = 625 elements, the Routes API limit per request


def place_id(rec):
    return rec.get("attraction_id") or rec.get("hotel_id") or rec.get("code")


def estimate(a, b):
    """{"minutes", "km", "source": "estimate"} from lat/lng alone; minutes rounded up to 5."""
    # ponytail: one city speed, no traffic or timetables; run the Google warm-up for real times
    lat1, lng1, lat2, lng2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    km = 2 * 6371 * math.asin(math.sqrt(h)) * ROAD_FACTOR
    minutes = OVERHEAD_MINUTES + km / CITY_KMH * 60
    return {"minutes": int(math.ceil(minutes / 5 - 1e-9) * 5), "km": round(km, 1), "source": "estimate"}


class Travel:
    def __init__(self, cache):
        self._cache = cache  # {(from_id, to_id): (minutes, meters, source)}
        self._estimates = {}

    def leg(self, a, b):
        key = (place_id(a), place_id(b))
        hit = self._cache.get(key)
        if hit:
            return {"minutes": hit[0], "km": round(hit[1] / 1000, 1), "source": hit[2]}
        if key not in self._estimates:  # the builder asks for the same pairs thousands of times
            self._estimates[key] = estimate(a, b)
        return dict(self._estimates[key])

    def minutes(self, a, b):
        return self.leg(a, b)["minutes"]


def for_catalog(cat):
    """One Travel per catalog repository (one request), reading the cache once."""
    if not hasattr(cat, "_travel"):
        from app.repositories.travel_repo import TravelRepository
        cat._travel = Travel(TravelRepository(cat.conn).get_all())
    return cat._travel


def fetch(origins, destinations, key):
    """[(from_id, to_id, minutes, meters, "google")] from one Routes API route-matrix call; [] when it fails."""
    point = lambda r: {"waypoint": {"location": {"latLng": {"latitude": r["lat"], "longitude": r["lng"]}}}}
    req = Request(MATRIX_URL, method="POST", data=json.dumps({
        "origins": [point(r) for r in origins], "destinations": [point(r) for r in destinations],
        "travelMode": "DRIVE"}).encode(), headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,condition"})
    try:
        with urlopen(req, timeout=30) as r:
            body = json.load(r)
    except (OSError, ValueError) as e:  # HTTPError (403: Routes API not enabled for the key) is an OSError
        log.warning("Routes API call failed: %s %s", e, getattr(e, "read", lambda: b"")()[:300])
        return []
    if not isinstance(body, list):
        log.warning("Routes API refused: %s", str(body)[:300])
        return []
    rows = []
    for el in body:
        if el.get("condition") == "ROUTE_EXISTS" and "duration" in el:
            o, d = origins[el.get("originIndex", 0)], destinations[el.get("destinationIndex", 0)]
            rows.append((place_id(o), place_id(d), math.ceil(float(el["duration"].rstrip("s")) / 60),
                         el.get("distanceMeters", 0), "google"))
    return rows


def warm(cat, repo, key, dry_run=False):
    """Fetches (Routes API) every pair of places inside each city (hotels, attractions, airports serving it) into the cache.
    Returns the number of pairs stored (or, with dry_run, the number of elements it would request)."""
    countries = cat.destinations["countries"]
    cities = [c["name"] for country in countries for c in country["cities"]]
    airports = cat.conn.execute("SELECT code, lat, lng, serves_cities FROM airports").fetchall()
    total = 0
    for city in cities:
        places = [dict(h) for h in cat.conn.execute("SELECT hotel_id, lat, lng FROM hotels WHERE city = %s "
                                                    "ORDER BY hotel_id", (city,)).fetchall()]
        places += [dict(a) for a in cat.attractions_in(city)]
        places += [dict(a) for a in airports if city in a["serves_cities"]]
        elements = len(places) ** 2
        print(f"{city}: {len(places)} places, {elements} elements")
        if dry_run:
            total += elements
            continue
        for i in range(0, len(places), BATCH):
            for j in range(0, len(places), BATCH):
                rows = fetch(places[i:i + BATCH], places[j:j + BATCH], key)
                repo.put_many(rows)
                total += len(rows)
        cat.conn.commit()
    return total


def main():
    from app.core import db
    from app.core.config import get_settings
    from app.repositories.catalog_repo import CatalogRepository
    from app.repositories.travel_repo import TravelRepository

    p = argparse.ArgumentParser(description="Fill the travel_times cache from the Google Routes API (route matrix).")
    p.add_argument("--warm", action="store_true", help="call Google and store the results")
    p.add_argument("--dry-run", action="store_true", help="only count the elements (each one is billed)")
    args = p.parse_args()
    key = get_settings().google_maps_key
    if not (args.warm or args.dry_run):
        p.error("use --warm or --dry-run")
    if args.warm and not key:
        p.error("set GOOGLE_MAP_API in the repo's .env (or GOOGLE_MAPS_KEY in the environment) first")
    db.init_db()  # creates travel_times on a database made before the table existed
    with db.connect() as conn:
        n = warm(CatalogRepository(conn), TravelRepository(conn), key, dry_run=args.dry_run)
    print(f"{'would request' if args.dry_run else 'stored'} {n} {'elements' if args.dry_run else 'pairs'}")


if __name__ == "__main__":
    main()
