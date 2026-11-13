"""Search, book and reopen packages. Nothing is stored before booking: the client keeps the package it was
given and sends its request and selection back to change or book it."""
import hashlib
import json
import logging
from typing import Any

from pydantic import ValidationError

from app.repositories.catalog_repo import CatalogRepository
from app.repositories.package_repo import PackageRepository
from app.schemas import selection as selection_schema
from app.services import builder, package, validator
from app.services.errors import NotFound
from app.services.request_form import InvalidRequest, validate_request

log = logging.getLogger(__name__)


def present(trip: dict, request: dict, selection: dict) -> dict:
    """The Package with what it takes to change or book it: the normalized request and the selection, as JSON."""
    wire = {**request, "start_date": request["start_date"].isoformat(), "end_date": request["end_date"].isoformat()}
    return {**trip, "request": wire, "selection": selection_schema.dump(selection)}


class PackageService:
    def __init__(self, cat: CatalogRepository, repo: PackageRepository):
        self._cat = cat
        self._repo = repo

    def search(self, raw: Any) -> dict:
        """Raises InvalidRequest, builder.NoPackage or builder.OverBudget."""
        request = validate_request(raw, self._cat)
        trip, selection = builder.build_selection(request, self._cat)
        return present(trip, request, selection)

    def search_many(self, raw: Any, limit: int = 30) -> dict:
        """{"packages", "picks"}: every package that fits (one per city plan), cheapest first, and for the cheapest,
        fastest and best rated one (G4) its position in "packages". Same errors as search()."""
        request = validate_request(raw, self._cat)
        built = builder.build_many(request, self._cat, limit)
        index = {}  # objective -> position in `built`; a pick that is already a candidate is not listed twice
        for objective, (trip, selection) in builder.build_picks(request, self._cat).items():
            known = next((n for n, b in enumerate(built) if b[1] == selection), None)
            if known is None:
                built.append((trip, selection))
                known = len(built) - 1
            index[objective] = known
        return {"packages": [present(t, request, s) for t, s in built], "picks": index}

    def rebuild(self, raw: Any) -> tuple[dict, dict]:
        """(request, selection) from a body {"request", "selection"}, checked against the catalog and every
        travel rule again: the client's copy is never trusted. Raises InvalidRequest."""
        if not isinstance(raw, dict) or not isinstance(raw.get("request"), dict) \
                or not isinstance(raw.get("selection"), dict):
            raise InvalidRequest("request", 'Send the package as {"request": ..., "selection": ...}, as search returned it.')
        request = validate_request(raw["request"], self._cat)
        try:
            selection = selection_schema.parse(raw["selection"])
            problems = validator.validate(package.assemble(request, selection, self._cat), self._cat, first_package=False)
        except ValidationError as e:
            err = e.errors()[0]
            raise InvalidRequest("selection", f"selection.{'.'.join(map(str, err['loc']))}: {err['msg']}.") from None
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):  # an id the catalog does not have
            raise InvalidRequest("selection", "The selection names a flight, hotel, room, transfer or attraction "
                                              "that does not exist.") from None
        # availability is decided by the booking transaction (SoldOut, 409), which takes the seats and rooms atomically
        problems = [p for p in problems if not p.startswith(("FLIGHT_SEATS", "ROOM_AVAILABILITY"))]
        if problems:
            raise InvalidRequest("selection", problems[0].split(": ", 1)[1])
        return request, selection

    def book(self, raw: Any, key: str) -> tuple[str, dict]:
        """Books the package in one transaction. Raises InvalidRequest, errors.IdempotencyKeyReused or
        errors.SoldOut (then nothing is booked)."""
        request, selection = self.rebuild(raw)
        trip = package.assemble(request, selection, self._cat)
        payload = json.dumps(present({}, request, selection), sort_keys=True)
        reference = self._repo.book(request, selection, trip, self._cat.country(request["country"])["code"], key,
                                    hashlib.sha256(payload.encode()).hexdigest())
        log.info("Booked %s: %s to %s, %s, %d nights, total %d", reference, request["departure_city"],
                 request["country"], request["start_date"], request["nights"], trip["total_inr"])
        return reference, self.reservation(reference)

    def reservation(self, reference: str) -> dict:
        found = self._repo.load(reference) if reference.isdigit() and len(reference) == 10 else None
        if not found:
            raise NotFound("Reservation")
        b, selection = found
        request = {"departure_city": b["home_airport"], "country": self._cat.country_name(b["country_code"]),
                   "start_date": b["start_date"], "end_date": b["end_date"], "nights": b["nights"],
                   "adults": b["adults"], "child_ages": b["child_ages"], "budget_inr": b["budget_inr"]}
        return package.assemble(request, selection, self._cat, reference=b["reference"])

    def reservations(self) -> list[dict]:
        return [self.reservation(r) for r in self._repo.references()]
