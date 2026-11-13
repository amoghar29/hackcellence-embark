"""Changing a package (Phase 2): alternatives with price differences, and one change at a time.

Nothing is saved. Every call gets the package's request and selection (see PackageService.rebuild) and returns
the answer; the client keeps the new package.
"""
from datetime import date
from typing import Any

from app.repositories.catalog_repo import CatalogRepository
from app.services import changes, package
from app.services.package_service import PackageService, present
from app.services.request_form import InvalidRequest


class _HeldCatalog:
    """The catalog as a booking sees it while it is being changed: the seats and rooms it already holds count as
    free, so keeping its own flight or room is never refused as sold out. Everything else is the real catalog."""
    def __init__(self, cat: CatalogRepository, seats: dict, rooms: dict):
        self._cat, self._seats, self._rooms = cat, seats, rooms

    def __getattr__(self, name):
        return getattr(self._cat, name)

    def _free(self, f):
        return f and {**f, "seats_left": f["seats_left"] + self._seats.get(f["flight_id"], 0)}

    def get_flight(self, flight_id):
        return self._free(self._cat.get_flight(flight_id))

    def flights(self, *args):
        return [self._free(f) for f in self._cat.flights(*args)]

    def rooms_left(self, room_id, night):
        return self._cat.rooms_left(room_id, night) + self._rooms.get((room_id, night), 0)


class ChangeService:
    def __init__(self, cat: CatalogRepository, packages: PackageService):
        self._real = cat
        self._packages = packages

    def _for(self, raw: Any) -> "ChangeService":
        """Changing a booking (the body names its "reference"): its own seats and rooms count as free."""
        ref = raw.get("reference") if isinstance(raw, dict) else None
        self._cat = _HeldCatalog(self._real, *self._packages.held(str(ref))) if ref else self._real
        return self

    def apply(self, raw: Any, change: dict) -> dict:
        """Raises InvalidRequest or changes.Refused; a refused change leaves the package as it was."""
        self._for(raw)
        request, selection = self._packages.rebuild(raw)
        new = changes.apply(request, selection, change, self._cat)
        # G1: what was fixed or must be known (a visit removed, experiences re-picked); early check-ins sit on the items
        return {**present(package.assemble(request, new, self._cat), request, new),
                "notices": changes.notices(request, selection, new, change, self._cat)}

    def _previewed(self, raw: Any, options: list[dict], body) -> list[dict]:
        """Only options the change call accepts, each with the package it gives (what changes, what is removed,
        the new total). Same check as apply(), so a listed option is never refused."""
        out = []
        for o in options:
            try:
                out.append({**o, "preview": self.apply(raw, body(o))})
            except changes.Refused:
                continue
        return out

    def city_plan_options(self, raw: Any) -> list[dict]:
        self._for(raw)
        request, selection = self._packages.rebuild(raw)
        total = package.assemble(request, selection, self._cat)["total_inr"]
        found = changes.city_plan_options(request, selection, total, self._cat)
        current = [o for o in found if o["is_current"]]
        return current + self._previewed(raw, [o for o in found if not o["is_current"]],
                                         lambda o: {"action": "change_city_plan", "plan": o["plan"]})

    def hotel_options(self, raw: Any, city: str) -> list[dict]:
        self._for(raw)
        request, selection = self._packages.rebuild(raw)
        found = changes.hotel_options(request, selection, city, self._cat)
        if found is None:
            raise InvalidRequest("city", f"{city} is not a city of this package.")
        return self._previewed(raw, found, lambda o: {"action": "change_hotel", "city": city,
                                                      "hotel_id": o["hotel_id"], "room_id": o["room_id"]})

    def flight_options(self, raw: Any, direction: str) -> list[dict]:
        self._for(raw)
        request, selection = self._packages.rebuild(raw)
        item_id = "flight-arrival" if direction == "ARRIVAL" else "flight-return"
        return self._previewed(raw, changes.flight_options(request, selection, direction, self._cat),
                               lambda o: {"action": "change_flight", "item_id": item_id, "flight_id": o["flight_id"]})

    def attraction_options(self, raw: Any, day: date) -> dict:
        """{"options", "reason"}: reason says why the day has no option, else None."""
        self._for(raw)
        request, selection = self._packages.rebuild(raw)
        found = self._previewed(raw, changes.attraction_options(request, selection, day, self._cat),
                                lambda o: {"action": "add_attraction", "attraction_id": o["attraction_id"],
                                           "start": o["start"]})
        return {"options": found,
                "reason": None if found else changes.no_attraction_reason(request, selection, day, self._cat)}
