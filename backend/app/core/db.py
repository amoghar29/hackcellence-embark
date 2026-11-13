"""Postgres connections. The SQL scripts live in db/ at the repo root (docker also runs them on first start)."""
import psycopg
from psycopg.rows import dict_row

from app.core.config import SQL_DIR, get_settings


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url, row_factory=dict_row)


def run_script(name: str) -> None:
    with connect() as conn:
        conn.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def init_db() -> None:
    run_script("01_schema.sql")
