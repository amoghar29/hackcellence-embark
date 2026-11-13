"""The read-only catalog tables. Each method runs its own SELECT; nothing is loaded up front.

One repository per request, on one connection. The builder asks the same questions many times while it
searches, so a query's rows are kept for the rest of the request (the catalog does not change after seeding).
Departure cities, country links and rules are not tables; they come from destinations.json (see db/01_schema.sql).
"""
import json
from functools import cache

import psycopg

from app.core.config import CATALOG_DIR, IMAGES_DIR


@cache
def _destinations() -> dict:
    return json.loads((CATALOG_DIR / "destinations.json").read_text(encoding="utf-8"))


class CatalogRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        self._seen = {}

    def _rows(self, sql: str, *args) -> list[dict]:
        key = (sql, *(tuple(a) if isinstance(a, list) else a for a in args))
        if key not in self._seen:
            self._seen[key] = self.conn.execute(sql, args).fetchall()
        return self._seen[key]

    def _one(self, sql: str, *args) -> dict | None:
        rows = self._rows(sql, *args)
        return rows[0] if rows else None

    # ---------- one row by id (None when unknown) ----------

    def get_flight(self, flight_id):
        return self._one("SELECT * FROM flights WHERE flight_id = %s", flight_id)

    def get_hotel(self, hotel_id):
        h = self._one("SELECT * FROM hotels WHERE hotel_id = %s", hotel_id)
        return h and dict(h, rating=float(h["rating"]))

    def get_room(self, room_id):
        return self._one("SELECT * FROM rooms WHERE room_id = %s", room_id)

    def get_transfer(self, transfer_id):
        return self._one("SELECT * FROM transfers WHERE transfer_id = %s", transfer_id)

    def get_attraction(self, attraction_id):
        return self._one("SELECT * FROM attractions WHERE attraction_id = %s", attraction_id)

    def get_airport(self, code):
        return self._one("SELECT * FROM airports WHERE code = %s", code)

    # ---------- searches ----------

    def flights(self, home, cities, day, arriving):
        """Arriving: from home, landing on day at an airport serving one of the cities.
        Returning: to home, leaving on day from such an airport. Days are local dates."""
        here, there, when = ("from_airport", "to_airport", "arrival_local") if arriving else \
                            ("to_airport", "from_airport", "departure_local")
        return self._rows(f"SELECT f.* FROM flights f JOIN airports a ON a.code = f.{there} "
                          f"WHERE f.{here} = %s AND f.{when}::date = %s AND a.serves_cities && %s::text[] "
                          "ORDER BY f.flight_id", home, day, list(cities))

    def rooms_in(self, city):
        return self._rows("SELECT r.* FROM rooms r JOIN hotels h USING (hotel_id) WHERE h.city = %s "
                          "ORDER BY r.room_id", city)

    def rooms_of(self, hotel_id):
        return self._rows("SELECT * FROM rooms WHERE hotel_id = %s ORDER BY room_id", hotel_id)

    def rooms_left(self, room_id, night):
        row = self._one("SELECT rooms_left FROM availability WHERE room_id = %s AND date = %s", room_id, night)
        return row["rooms_left"] if row else 0

    def airport_transfers(self, airport, city, area):
        """Transfers between the airport and the city that serve the area (area NULL = every area)."""
        return self._rows("SELECT * FROM transfers WHERE airport = %s AND city = %s AND (area IS NULL OR area = %s) "
                          "ORDER BY transfer_id", airport, city, area)

    def attractions_in(self, city):
        return self._rows("SELECT * FROM attractions WHERE city = %s ORDER BY attraction_id", city)

    def list_attractions(self):
        return self._rows("SELECT * FROM attractions ORDER BY attraction_id")

    def serves(self, airport, city):
        return city in self.get_airport(airport)["serves_cities"]

    # ---------- destinations.json ----------

    @property
    def destinations(self) -> dict:
        return _destinations()

    def country(self, name):
        return next(c for c in self.destinations["countries"] if c["name"] == name)

    def country_name(self, code):
        return next(c["name"] for c in self.destinations["countries"] if c["code"] == code)

    def home_city(self, airport):
        return next(d["city"] for d in self.destinations["departure_cities"] if d["airport"] == airport)


def load_credits() -> str:
    return (IMAGES_DIR / "ATTRIBUTIONS.md").read_text(encoding="utf-8")
