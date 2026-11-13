"""Build My Holiday backend. Start from backend/ with Postgres running: uvicorn app.main:app --reload"""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.routers import catalog, packages, reservations
from app.core.config import IMAGES_DIR, get_settings
from app.core.logging_config import configure_logging
from app.repositories.catalog_repo import load_catalog

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cat = load_catalog()
    app.state.catalog = cat
    log.info("Catalog loaded: %d flights, %d hotels, %d rooms, %d transfers, %d attractions",
             len(cat.flights), len(cat.hotels), len(cat.rooms), len(cat.transfers), len(cat.attractions))
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Build My Holiday", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"],
                       allow_headers=["*"])
    register_exception_handlers(app)
    for module in (catalog, packages, reservations):
        app.include_router(module.router)
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
    return app


app = create_app()
