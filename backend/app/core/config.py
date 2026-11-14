import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = ROOT / "db"
DATA_DIR = ROOT / "data" / "hackathon-problem-1-holiday-package"
CATALOG_DIR = DATA_DIR / "data" / "catalog"
IMAGES_DIR = DATA_DIR / "images"


@lru_cache
def _dotenv() -> dict:
    """KEY=value lines of the repo's .env (gitignored), for settings not set in the environment."""
    path = ROOT / ".env"
    if not path.exists():
        return {}
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    pairs = (line.split("=", 1) for line in lines if line and not line.startswith("#") and "=" in line)
    return {k.strip(): v.strip().strip("'\"") for k, v in pairs}


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql://embark:embark@localhost:5432/embark"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(o.strip() for o in _env("CORS_ORIGINS", "*").split(",")))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())
    # required: every travel time comes from the Google Routes API
    google_maps_key: str = field(default_factory=lambda: os.environ.get("GOOGLE_MAPS_KEY")
                                 or os.environ.get("GOOGLE_MAP_API") or _dotenv().get("GOOGLE_MAP_API", ""))


@lru_cache
def get_settings() -> Settings:
    return Settings()
