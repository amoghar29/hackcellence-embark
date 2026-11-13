import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = ROOT / "db"
DATA_DIR = ROOT / "data" / "hackathon-problem-1-holiday-package"
CATALOG_DIR = DATA_DIR / "data" / "catalog"
IMAGES_DIR = DATA_DIR / "images"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql://embark:embark@localhost:5432/embark"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(o.strip() for o in _env("CORS_ORIGINS", "*").split(",")))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())


@lru_cache
def get_settings() -> Settings:
    return Settings()
