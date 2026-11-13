"""Changing a saved package (Phase 2): alternatives with price differences, and one change at a time."""
import logging
from datetime import date

from app.repositories.catalog_repo import CatalogRepository
from app.repositories.package_repo import PackageRepository
from app.services import changes, package
from app.services.errors import AlreadyBooked
from app.services.package_service import PackageService
from app.services.request_form import InvalidRequest

log = logging.getLogger(__name__)


class ChangeService:
    def __init__(self, cat: CatalogRepository, packages: PackageService, repo: PackageRepository):
        self._cat = cat
        self._packages = packages
        self._repo = repo

    def apply(self, trip_id: str, change: dict) -> dict:
        """Raises NotFound, AlreadyBooked or changes.Refused; a refused change leaves the package as it was."""
        saved = self._packages.open(trip_id)
        if saved.trip["status"] == "BOOKED":
            raise AlreadyBooked()
        selection = changes.apply(saved.request, saved.selection, change, self._cat)
        self._repo.update(trip_id, selection, package.assemble(trip_id, saved.request, selection, self._cat))
        log.info("Package %s changed: %s", trip_id, change["action"])
        return self._packages.get(trip_id)

    def hotel_options(self, trip_id: str, city: str) -> list[dict]:
        saved = self._packages.open(trip_id)
        found = changes.hotel_options(saved.request, saved.selection, city, self._cat)
        if found is None:
            raise InvalidRequest("city", f"{city} is not a city of this package.")
        return found

    def flight_options(self, trip_id: str, direction: str) -> list[dict]:
        saved = self._packages.open(trip_id)
        return changes.flight_options(saved.request, saved.selection, direction, self._cat)

    def attraction_options(self, trip_id: str, day: date) -> list[dict]:
        saved = self._packages.open(trip_id)
        return changes.attraction_options(saved.request, saved.selection, day, self._cat)
