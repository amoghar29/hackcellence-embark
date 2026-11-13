"""Maps domain errors to the one error shape of docs/API.md: {"code", "error", ...}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.services.builder import NoPackage, OverBudget
from app.services.changes import Refused
from app.services.errors import AlreadyBooked, IdempotencyKeyReused, NotFound, SoldOut
from app.services.request_form import InvalidRequest

log = logging.getLogger(__name__)


def _error(request: Request, status: int, code: str, error: str, **extra) -> JSONResponse:
    log.info("%s %s -> %d %s: %s", request.method, request.url.path, status, code, error)
    return JSONResponse({"code": code, "error": error, **extra}, status_code=status)


def _invalid_request(request: Request, e: InvalidRequest) -> JSONResponse:
    return _error(request, 400, "INVALID_REQUEST", str(e), field=e.field)


def _validation_error(request: Request, e: RequestValidationError) -> JSONResponse:
    first = e.errors()[0]
    loc = [part for part in first["loc"][1:] if isinstance(part, str)]
    field = loc[-1] if loc else None
    if first["type"].startswith("union_tag"):
        field = first["ctx"]["discriminator"].strip("'")
    return _error(request, 400, "INVALID_REQUEST", f"{field or 'Request'}: {first['msg']}.", field=field)


def _not_found(request: Request, e: NotFound) -> JSONResponse:
    return _error(request, 404, "NOT_FOUND", str(e))


def _http_error(request: Request, e: HTTPException) -> JSONResponse:
    if e.status_code == 404:
        return _error(request, 404, "NOT_FOUND", "Page not found.")
    return _error(request, e.status_code, "INVALID_REQUEST", str(e.detail))


def _no_package(request: Request, e: NoPackage) -> JSONResponse:
    return _error(request, 422, "NO_PACKAGE", e.reasons[0], reasons=e.reasons, blockers=e.blockers,
                  suggestion=e.suggestion, alternatives=e.alternatives)


def _over_budget(request: Request, e: OverBudget) -> JSONResponse:
    return _error(request, 422, "OVER_BUDGET", str(e), budget_inr=e.budget_inr,
                  cheapest_total_inr=e.cheapest_total_inr, over_by_inr=e.cheapest_total_inr - e.budget_inr,
                  suggestion=e.suggestion, alternatives=e.alternatives)


def _change_refused(request: Request, e: Refused) -> JSONResponse:
    return _error(request, 422, "CHANGE_REFUSED", e.reasons[0], reasons=e.reasons, blockers=e.blockers)


def _already_booked(request: Request, e: AlreadyBooked) -> JSONResponse:
    return _error(request, 409, "ALREADY_BOOKED", str(e))


def _sold_out(request: Request, e: SoldOut) -> JSONResponse:
    return _error(request, 409, "SOLD_OUT", str(e), part=e.part)


def _key_reused(request: Request, e: IdempotencyKeyReused) -> JSONResponse:
    return _error(request, 409, "IDEMPOTENCY_KEY_REUSED", str(e))


def _unexpected(request: Request, e: Exception) -> JSONResponse:
    return JSONResponse({"code": "INTERNAL_ERROR", "error": "Something went wrong. Try again."}, status_code=500)


HANDLERS = {
    InvalidRequest: _invalid_request,
    RequestValidationError: _validation_error,
    NotFound: _not_found,
    HTTPException: _http_error,
    NoPackage: _no_package,
    OverBudget: _over_budget,
    Refused: _change_refused,
    AlreadyBooked: _already_booked,
    SoldOut: _sold_out,
    IdempotencyKeyReused: _key_reused,
    Exception: _unexpected,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc, handler in HANDLERS.items():
        app.add_exception_handler(exc, handler)
