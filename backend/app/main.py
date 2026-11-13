"""Build My Holiday backend. Start from backend/ with Postgres running: uvicorn app.main:app --reload"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.routers import bookings, catalog, packages, reservations
from app.core.config import IMAGES_DIR, get_settings
from app.core.logging_config import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Build My Holiday")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"],
                       allow_headers=["*"])
    register_exception_handlers(app)
    for module in (catalog, packages, bookings, reservations):
        app.include_router(module.router)
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
    return app


app = create_app()
