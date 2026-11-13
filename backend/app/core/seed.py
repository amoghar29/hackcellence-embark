"""Loads data/catalog/*.json into the catalog tables. Safe to run again (existing rows are kept)."""
from app.core import db


def seed() -> None:
    db.run_script("02_seed.sql")
