from typing import Annotated, Any

from fastapi import APIRouter, Body, Header

from app.api.deps import PackageServiceDep
from app.schemas.booking import PackageBody
from app.schemas.responses import Booking

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


# The body is parsed in the service: its rules need the catalog. openapi_extra documents the shape.
@router.post("", openapi_extra={"requestBody": {
    "required": True, "content": {"application/json": {"schema": PackageBody.model_json_schema()}}}})
def book(service: PackageServiceDep,
         idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
         body: Annotated[Any, Body()] = None) -> Booking:
    reference, trip = service.book(body, idempotency_key)
    return Booking(reference=reference, package=trip)
