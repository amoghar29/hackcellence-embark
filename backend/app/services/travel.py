"""Travel time between two catalog places (hotels, attractions, airports: anything with lat/lng).

Every time comes from the Google Routes API (key: GOOGLE_MAP_API in the repo's .env, Routes API enabled); there
is no formula estimate. Search reads the travel_times cache and fetches any missing pair from Google on the spot,
saving it. The warm-up prefills the cache so search rarely waits on Google:

    uv run python -m app.services.travel --warm
"""
import argparse
import json
import logging
import math
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

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


class TravelUnavailable(RuntimeError):
    """Google gave no travel time for a pair (no key, network or API error, no route)."""


def save(rows):
    """Stores fetched legs in travel_times on a connection of their own (the request's may roll back)."""
    from app.core import db
    from app.repositories.travel_repo import TravelRepository
    with db.connect() as conn:
        TravelRepository(conn).put_many(rows)


class Travel:
    def __init__(self, cache, key, save):
        self._cache = cache  # {(from_id, to_id): (minutes, meters, source)}
        self._key, self._save = key, save

    def leg(self, a, b):
        pair = (place_id(a), place_id(b))
        if pair not in self._cache:
            # ponytail: one Routes API call per missing pair; run --warm so search rarely gets here
            rows = fetch([a], [b], self._key) if self._key else []
            if not rows:
                raise TravelUnavailable(f"Google gave no travel time from {pair[0]} to {pair[1]}.")
            self._save(rows)
            self._cache[pair] = rows[0][2:]
        minutes, meters, source = self._cache[pair]
        return {"minutes": minutes, "km": round(meters / 1000, 1), "source": source}

    def minutes(self, a, b):
        return self.leg(a, b)["minutes"]


def for_catalog(cat):
    """One Travel per catalog repository (one request), reading the cache once."""
    if not hasattr(cat, "_travel"):
        from app.core.config import get_settings
        from app.repositories.travel_repo import TravelRepository
        cat._travel = Travel(TravelRepository(cat.conn).get_all(), get_settings().google_maps_key, save)
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
