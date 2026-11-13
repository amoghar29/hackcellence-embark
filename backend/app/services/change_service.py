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


class ChangeService:
    def __init__(self, cat: CatalogRepository, packages: PackageService):
        self._cat = cat
        self._packages = packages

    def apply(self, raw: Any, change: dict) -> dict:
        """Raises InvalidRequest or changes.Refused; a refused change leaves the package as it was."""
        request, selection = self._packages.rebuild(raw)
        new = changes.apply(request, selection, change, self._cat)
        # G1: what was fixed or must be known (a visit removed, experiences re-picked); early check-ins sit on the items
        return {**present(package.assemble(request, new, self._cat), request, new),
                "notices": changes.notices(request, selection, new, change, self._cat)}

    def city_plan_options(self, raw: Any) -> list[dict]:
        request, selection = self._packages.rebuild(raw)
        total = package.assemble(request, selection, self._cat)["total_inr"]
        return changes.city_plan_options(request, selection, total, self._cat)

    def hotel_options(self, raw: Any, city: str) -> list[dict]:
        request, selection = self._packages.rebuild(raw)
        found = changes.hotel_options(request, selection, city, self._cat)
        if found is None:
            raise InvalidRequest("city", f"{city} is not a city of this package.")
        return found

    def flight_options(self, raw: Any, direction: str) -> list[dict]:
        request, selection = self._packages.rebuild(raw)
        return changes.flight_options(request, selection, direction, self._cat)

    def attraction_options(self, raw: Any, day: date) -> list[dict]:
        request, selection = self._packages.rebuild(raw)
        return changes.attraction_options(request, selection, day, self._cat)
