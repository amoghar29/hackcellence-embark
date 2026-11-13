"""Read-only catalog views: form options, detail records and photo credits."""
from app.core.timeutil import fmt
from app.repositories import catalog_repo
from app.repositories.catalog_repo import CatalogRepository
from app.services.errors import NotFound


class CatalogService:
    def __init__(self, cat: CatalogRepository):
        self._cat = cat

    def options(self) -> dict:
        d = self._cat.destinations
        r = d["rules"]
        return {"departure_cities": d["departure_cities"], "countries": [c["name"] for c in d["countries"]],
                "rules": {"min_nights": r["min_nights"], "max_nights": r["max_nights"],
                          "min_nights_per_city": r["min_nights_per_city"], **r["data_window"]}}

    def hotel(self, hotel_id: str) -> dict:
        h = self._record(self._cat.get_hotel(hotel_id), "Hotel")
        rooms = [{"room_id": r["room_id"], "room_type": r["room_type"], "name": r["name"],
                  "max_adults": r["max_adults"], "max_children": r["max_children"],
                  "price_per_night_inr": r["price_inr"], "refundable": r["refundable"]}
                 for r in self._cat.rooms_of(hotel_id)]
        return {**h, "image": "/" + h["image"], "rooms": rooms}

    def flight(self, flight_id: str) -> dict:
        f = self._record(self._cat.get_flight(flight_id), "Flight")
        return {**{k: v for k, v in f.items() if k != "price_inr"},
                "from_airport_name": self._cat.get_airport(f["from_airport"])["name"],
                "to_airport_name": self._cat.get_airport(f["to_airport"])["name"],
                "departure_local": fmt(f["departure_local"]), "arrival_local": fmt(f["arrival_local"]),
                "price_per_seat_inr": f["price_inr"]}

    def transfer(self, transfer_id: str) -> dict:
        return self._record(self._cat.get_transfer(transfer_id), "Transfer")

    def attraction(self, attraction_id: str) -> dict:
        a = self._record(self._cat.get_attraction(attraction_id), "Attraction")
        return {**{k: v for k, v in a.items() if k != "price_inr"},
                "closed_dates": [d.isoformat() for d in a["closed_dates"]],
                "price_per_person_inr": a["price_inr"], "image": "/" + a["image"]}

    @staticmethod
    def credits() -> str:
        return catalog_repo.load_credits()

    @staticmethod
    def _record(rec: dict | None, what: str) -> dict:
        if rec is None:
            raise NotFound(what)
        return rec
