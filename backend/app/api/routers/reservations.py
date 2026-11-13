from fastapi import APIRouter

from app.api.deps import PackageServiceDep

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


@router.get("")
def my_bookings(service: PackageServiceDep) -> dict:
    return {"reservations": service.reservations()}


@router.get("/{reference}")
def reservation(reference: str, service: PackageServiceDep) -> dict:
    return service.reservation(reference)
