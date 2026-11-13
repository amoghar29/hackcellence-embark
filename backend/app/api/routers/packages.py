from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Query, Response, status

from app.api.deps import ChangeServiceDep, PackageServiceDep
from app.schemas.change import Change
from app.services.errors import NotFound

router = APIRouter(prefix="/api/packages", tags=["packages"])

PARTS = {"flights": "flight", "hotels": "hotel", "transfers": "transfer", "attractions": "attraction"}


@router.post("/search", status_code=status.HTTP_201_CREATED)
def search(service: PackageServiceDep, body: Annotated[Any, Body()] = None) -> dict:
    """The body stays raw: request_form validates and normalizes it with field-level messages."""
    return service.search(body)


@router.get("/{trip_id}")
def get_package(trip_id: str, service: PackageServiceDep) -> dict:
    return service.get(trip_id)


@router.patch("/{trip_id}")
def change_package(trip_id: str, change: Annotated[Change, Body()], service: ChangeServiceDep) -> dict:
    return service.apply(trip_id, change.model_dump())


@router.get("/{trip_id}/export")
def export(trip_id: str, response: Response, service: PackageServiceDep) -> dict:
    trip = service.export(trip_id)
    response.headers["Content-Disposition"] = f'attachment; filename="trip-{trip_id}.json"'
    return trip


@router.post("/{trip_id}/book")
def book(trip_id: str, service: PackageServiceDep) -> dict:
    reference, trip = service.book(trip_id)
    return {"reference": reference, "package": trip}


@router.get("/{trip_id}/days")
def days(trip_id: str, service: PackageServiceDep) -> dict:
    return {"trip_id": trip_id, "days": service.get(trip_id)["days"]}


@router.get("/{trip_id}/options/hotels")
def hotel_options(trip_id: str, city: str, service: ChangeServiceDep) -> dict:
    return {"trip_id": trip_id, "options": service.hotel_options(trip_id, city)}


@router.get("/{trip_id}/options/flights")
def flight_options(trip_id: str, service: ChangeServiceDep,
                   direction: Literal["ARRIVAL", "RETURN"] = "ARRIVAL") -> dict:
    return {"trip_id": trip_id, "options": service.flight_options(trip_id, direction)}


@router.get("/{trip_id}/options/attractions")
def attraction_options(trip_id: str, day: Annotated[date, Query(alias="date")], service: ChangeServiceDep) -> dict:
    return {"trip_id": trip_id, "options": service.attraction_options(trip_id, day)}


@router.get("/{trip_id}/{part}")
def package_part(trip_id: str, part: str, service: PackageServiceDep) -> dict:
    if part not in PARTS:
        raise NotFound("Page")
    return {"trip_id": trip_id, "items": service.items(trip_id, PARTS[part])}
