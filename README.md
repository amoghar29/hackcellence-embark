# hackcellence-embark

## Rule checks

- `python backend/tests/check_trip.py trip.json`: checks an exported package against every travel rule (add `--edited` for a package the traveler changed).
- `docker compose up -d`, then `cd backend && uv run pytest`: all tests (they use their own database, `embark_test`). Each package the backend returns must pass the checker. Phase 1 only: `uv run pytest --ignore=tests/test_api_changes.py`.

## API

The API contract (endpoints, requests, responses, errors) is in [docs/API.md](docs/API.md).

## Day plans and travel times

Each day is planned as a trip you can actually take. The traveler leaves the hotel, visits the nearest stop first, and allows travel time between stops plus 15 minutes after each visit. Every visit ends at least 30 minutes before closing, and the traveler is back at the hotel by 20:00. Arrival and city-change days get a visit only when the traveler reaches the city early enough. If a traveler adds a visit with no time to get there, the package keeps it and shows a warning. Constants are at the top of `backend/app/services/travel.py`.

Without Google data, travel times are estimated from the catalog's lat/lng (straight line × 1.4, at 20 km/h, plus 10 minutes). This needs no key and gives the same plan every run. For real road times from Google (optional):

1. Put `GOOGLE_MAP_API=...` in the repo's `.env` (gitignored; never commit or zip it). In the key's Google Cloud project, enable the **Routes API** (travel times) and the **Maps JavaScript API** (the map).
2. `cd backend && uv run python -m app.services.travel --dry-run` shows how many elements it would request (about 2,550 for the whole catalog, billed by Google per element). Then run `uv run python -m app.services.travel --warm` once.

With the key, the trip map is Google Maps in English. Without it, or if Google refuses the key, the map falls back to OpenStreetMap with English labels. The key ends up in the built frontend, as every browser Maps key does, so restrict it to your site's referrers in Google Cloud.

The warm-up stores the results in the `travel_times` table. Search only reads that table and never calls Google, so it stays fast and works offline. In the UI, each leg has a "Directions" link to Google Maps (no key needed); legs without Google data are marked "estimate".

## Database

`db/01_schema.sql` (tables, one column per field) and `db/02_seed.sql` (loads `data/catalog/*.json`) run when the Postgres volume is first created. Catalog tables have the same names as the catalog files. After a schema change, recreate the volume: `docker compose down -v && docker compose up -d` (this deletes saved bookings).
