"""Search, reopen and book packages."""
import logging
from typing import Any, NamedTuple

from app.repositories.catalog_repo import CatalogRepository
from app.repositories.package_repo import PackageRepository
from app.services import builder, package
from app.services.errors import NotFound
from app.services.request_form import validate_request

log = logging.getLogger(__name__)


class SavedPackage(NamedTuple):
    request: dict
    selection: dict
    trip: dict


class PackageService:
    def __init__(self, cat: CatalogRepository, repo: PackageRepository):
        self._cat = cat
        self._repo = repo

    def search(self, raw: Any) -> dict:
        """Raises InvalidRequest, builder.NoPackage or builder.OverBudget."""
        request = validate_request(raw, self._cat)
        trip, selection = builder.build_selection(request, self._cat)
        trip_id = self._repo.save(request, selection, trip, self._cat.country(request["country"])["code"])
        log.info("Package %s saved: %s to %s, %s, %d nights, total %d", trip_id, request["departure_city"],
                 request["country"], request["start_date"], request["nights"], trip["total_inr"])
        return self.get(trip_id)

    def search_many(self, raw: Any, limit: int = 30) -> list[dict]:
        """Every package that fits (one per city plan), cheapest first, each saved. Same errors as search()."""
        request = validate_request(raw, self._cat)
        code = self._cat.country(request["country"])["code"]
        built = builder.build_many(request, self._cat, limit)
        ids = [self._repo.save(request, selection, trip, code) for trip, selection in built]
        log.info("Search saved %d packages: %s to %s, %s, %d nights", len(ids), request["departure_city"],
                 request["country"], request["start_date"], request["nights"])
        return [self.get(i) for i in ids]

    def open(self, trip_id: str) -> SavedPackage:
        found = self._repo.load(trip_id)
        if not found:
            raise NotFound("Package")
        b, selection = found
        request = {"departure_city": b["home_airport"], "country": self._cat.country_name(b["country_code"]),
                   "start_date": b["start_date"], "end_date": b["end_date"], "nights": b["nights"],
                   "adults": b["adults"], "child_ages": b["child_ages"], "budget_inr": b["budget_inr"]}
        trip = package.assemble(trip_id, request, selection, self._cat, reference=b["reference"])
        return SavedPackage(request, selection, trip)

    def get(self, trip_id: str) -> dict:
        return self.open(trip_id).trip

    def items(self, trip_id: str, type_: str) -> list[dict]:
        return [i for i in self.get(trip_id)["items"] if i["type"] == type_]

    def book(self, trip_id: str, key: str) -> tuple[str, dict]:
        """Raises NotFound, errors.IdempotencyKeyReused or errors.SoldOut (then nothing is booked)."""
        reference = self._repo.book(trip_id, key)
        if not reference:
            raise NotFound("Package")
        log.info("Package %s booked as %s", trip_id, reference)
        return reference, self.get(trip_id)

    def reservations(self) -> list[dict]:
        return [self.get(i) for i in self._repo.booked_trip_ids()]

    def reservation(self, reference: str) -> dict:
        trip_id = self._repo.trip_id_for(reference) if reference.isdigit() and len(reference) == 10 else None
        if not trip_id:
            raise NotFound("Reservation")
        return self.get(trip_id)
