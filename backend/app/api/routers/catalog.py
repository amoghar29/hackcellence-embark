from fastapi import APIRouter

from app.api.deps import CatalogServiceDep
from app.schemas.responses import Credits, FormOptions

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/options")
def options(service: CatalogServiceDep) -> FormOptions:
    return FormOptions.model_validate(service.options())


@router.get("/hotels/{hotel_id}")
def hotel(hotel_id: str, service: CatalogServiceDep) -> dict:
    return service.hotel(hotel_id)


@router.get("/flights/{flight_id}")
def flight(flight_id: str, service: CatalogServiceDep) -> dict:
    return service.flight(flight_id)


@router.get("/transfers/{transfer_id}")
def transfer(transfer_id: str, service: CatalogServiceDep) -> dict:
    return service.transfer(transfer_id)


@router.get("/attractions/{attraction_id}")
def attraction(attraction_id: str, service: CatalogServiceDep) -> dict:
    return service.attraction(attraction_id)


@router.get("/credits")
def credits(service: CatalogServiceDep) -> Credits:
    return Credits(markdown=service.credits())
