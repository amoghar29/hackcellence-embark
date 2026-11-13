"""The read-only catalog, loaded once from Postgres into memory."""
import json
from dataclasses import dataclass

from app.core import db
from app.core.config import CATALOG_DIR, IMAGES_DIR


@dataclass
class Catalog:
    destinations: dict   # destinations.json as is: departure_cities, countries (cities, links), rules
    airports: dict       # code -> row
    flights: dict        # flight_id -> row (departure_local / arrival_local are local datetimes)
    hotels: dict         # hotel_id -> row
    rooms: dict          # room_id -> row
    availability: dict   # (room_id, night as date) -> rooms_left
    transfers: dict      # transfer_id -> row
    attractions: dict    # attraction_id -> row (closed_dates is a list of dates)

    def country(self, name):
        return next(c for c in self.destinations["countries"] if c["name"] == name)

    def country_name(self, code):
        return next(c["name"] for c in self.destinations["countries"] if c["code"] == code)

    def home_city(self, airport):
        return next(d["city"] for d in self.destinations["departure_cities"] if d["airport"] == airport)

    def serves(self, airport, city):
        return city in self.airports[airport]["serves_cities"]


def load_catalog():
    with db.connect() as conn:
        def table(name, key):
            return {r[key]: r for r in conn.execute(f"SELECT * FROM {name} ORDER BY {key}")}

        hotels = table("hotels", "hotel_id")
        for h in hotels.values():
            h["rating"] = float(h["rating"])
        return Catalog(
            # departure cities, links and rules are not tables; they come from the file (see db/01_schema.sql)
            destinations=json.loads((CATALOG_DIR / "destinations.json").read_text(encoding="utf-8")),
            airports=table("airports", "code"),
            flights=table("flights", "flight_id"),
            hotels=hotels,
            rooms=table("rooms", "room_id"),
            availability={(r["room_id"], r["date"]): r["rooms_left"]
                          for r in conn.execute("SELECT * FROM availability")},
            transfers=table("transfers", "transfer_id"),
            attractions=table("attractions", "attraction_id"),
        )


def load_credits() -> str:
    return (IMAGES_DIR / "ATTRIBUTIONS.md").read_text(encoding="utf-8")
