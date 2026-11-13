# hackcellence-embark

## Rule checks

- `python backend/tests/check_trip.py trip.json`: checks an exported package against every travel rule (add `--edited` for a package the traveler changed).
- `docker compose up -d`, then `cd backend && uv run pytest`: all tests (they use their own database, `embark_test`). Each package the backend returns must pass the checker. Phase 1 only: `uv run pytest --ignore=tests/test_api_changes.py`.

## API

The API contract (endpoints, requests, responses, errors) is in [docs/API.md](docs/API.md).

## Database

`db/01_schema.sql` (tables, one column per field) and `db/02_seed.sql` (loads `data/catalog/*.json`) run when the Postgres volume is first created. Catalog tables have the same names as the catalog files. After a schema change, recreate the volume: `docker compose down -v && docker compose up -d` (this deletes saved bookings).
