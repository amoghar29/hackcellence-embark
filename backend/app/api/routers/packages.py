from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Body, status

from app.api.deps import ChangeServiceDep, PackageServiceDep
from app.schemas.booking import PackageBody
from app.schemas.responses import AttractionOptions, CityPlanOptions, FlightOptions, HotelOptions
from app.schemas.search import SearchRequest
from app.services.request_form import InvalidRequest

router = APIRouter(prefix="/api/packages", tags=["packages"])


def _documents(model):
    return {"requestBody": {"required": True, "content": {"application/json": {"schema": model.model_json_schema()}}}}


# Bodies are parsed in the services: the rules need the catalog, which FastAPI cannot pass to a body model.
# openapi_extra still documents them. Nothing here is saved: a package lives in the client until it is booked.
@router.post("/search", status_code=status.HTTP_201_CREATED, openapi_extra=_documents(SearchRequest))
def search(service: PackageServiceDep, body: Annotated[Any, Body()] = None) -> dict:
    return service.search(body)


@router.post("/results", status_code=status.HTTP_201_CREATED, openapi_extra=_documents(SearchRequest))
def search_results(service: PackageServiceDep, body: Annotated[Any, Body()] = None) -> dict:
    found = service.search_many(body)
    return {"count": len(found["packages"]), **found}


# The next routes take {"request", "selection"} (and one more field) as search returned them.
@router.post("/change", openapi_extra=_documents(PackageBody))
def change_package(service: ChangeServiceDep, body: Annotated[Any, Body()] = None) -> dict:
    change = body.get("change") if isinstance(body, dict) else None
    return service.apply(body, change)


@router.post("/options/hotels", openapi_extra=_documents(PackageBody))
def hotel_options(service: ChangeServiceDep, body: Annotated[Any, Body()] = None) -> HotelOptions:
    city = body.get("city") if isinstance(body, dict) else None
    return HotelOptions(options=service.hotel_options(body, city))


@router.post("/options/city-plans", openapi_extra=_documents(PackageBody))
def city_plan_options(service: ChangeServiceDep, body: Annotated[Any, Body()] = None) -> CityPlanOptions:
    return CityPlanOptions(options=service.city_plan_options(body))


@router.post("/options/flights", openapi_extra=_documents(PackageBody))
def flight_options(service: ChangeServiceDep, body: Annotated[Any, Body()] = None) -> FlightOptions:
    direction = body.get("direction", "ARRIVAL") if isinstance(body, dict) else "ARRIVAL"
    if direction not in ("ARRIVAL", "RETURN"):
        raise InvalidRequest("direction", "Direction must be ARRIVAL or RETURN.")
    return FlightOptions(options=service.flight_options(body, direction))


@router.post("/options/attractions", openapi_extra=_documents(PackageBody))
def attraction_options(service: ChangeServiceDep, body: Annotated[Any, Body()] = None) -> AttractionOptions:
    try:
        day = date.fromisoformat(body["date"])
    except (TypeError, KeyError, ValueError):
        raise InvalidRequest("date", "Date must be a real date written as YYYY-MM-DD.") from None
    return AttractionOptions(**service.attraction_options(body, day))
