from fastapi import APIRouter

from app.api.deps import CatalogServiceDep

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/options")
def options(service: CatalogServiceDep) -> dict:
    return service.options()


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
def credits(service: CatalogServiceDep) -> dict:
    return {"markdown": service.credits()}
