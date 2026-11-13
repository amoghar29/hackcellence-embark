from typing import Annotated, Any

from fastapi import APIRouter, Body

from app.api.deps import PackageServiceDep
from app.schemas.booking import PackageBody

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


@router.get("")
def my_bookings(service: PackageServiceDep) -> dict:
    return {"reservations": service.reservations()}


@router.get("/{reference}")
def reservation(reference: str, service: PackageServiceDep) -> dict:
    return service.reservation(reference)


# M6 after booking: change the package with POST /api/packages/change, then save it here.
@router.put("/{reference}", openapi_extra={"requestBody": {
    "required": True, "content": {"application/json": {"schema": PackageBody.model_json_schema()}}}})
def modify(reference: str, service: PackageServiceDep, body: Annotated[Any, Body()] = None) -> dict:
    return service.modify(reference, body)
