# holiday.com: Build My Holiday

Enter a departure city, country, start date, nights, travelers and budget. The app chooses the cities and builds a complete holiday package (flights, hotels, airport and intercity transfers, attractions) that passes every travel rule. You can then change it and book it for a 10-digit reservation number.

## Start

Needs Docker only.

```
docker compose up -d
```

Open http://localhost:5173. The API is at http://localhost:8000 (`/docs` for Swagger). The first start takes a minute or two while the containers install packages and Postgres loads the catalog.

- Stop: `docker compose down`. Bookings are kept.
- Reset to an empty store (deletes bookings and the cached travel times): `docker compose down -v && docker compose up -d`.

## Architecture

```
frontend (React + Vite, :5173)  ──JSON──>  backend (FastAPI, :8000)  ──SQL──>  Postgres 17 (:5432)
  form, results, day plan,                  api/          routers, error shapes      catalog tables (seeded from
  change drawers, map, export               services/     builder, validator,         data/catalog/*.json),
                                                          pricing, changes, travel    bookings, travel_times
                                            repositories/ SQL only
                                            schemas/      request/response models
                                            core/         config, db, seed, time
```

- The backend holds all the logic: choosing cities, building, rule checks (`services/validator.py`) and prices (`services/pricing.py`). The frontend only displays and sends requests.
- A package has no id until it is booked. Search returns the package with its `request` and `selection`, and every change call sends those two back. The backend re-validates them, so the client is never trusted. Booking writes every part in one transaction, reduces seats and rooms (S2) and returns the reservation number.
- Every catalog record comes from `data/catalog/`, loaded into Postgres unchanged. The data files are never modified. No AI or LLM is called anywhere.

## City rule

`builder.city_plans` lists every city plan for the country:

- every ordered route of distinct cities that follows the catalog's `links` (so each city change has an intercity transfer)
- for each route, every split of the nights with at least 2 nights per city

For each plan, the builder picks the cheapest flights, hotels and transfers that satisfy the rules. It then plans 1–2 attractions per full day: the nearest stop first, with travel time in between, back at the hotel by 20:00. A second attraction, and one on an arrival or city-change day, is added only while the package stays within budget. Each finished package must pass `validator.validate()` or it is dropped.

Results show one package per plan that fits the budget, with three picks:

- **cheapest:** lowest total
- **fastest:** least flight minutes plus intercity transfer minutes
- **best rated:** highest average hotel stars per night

The "cheapest total" in the over-budget message is the bare package, without the optional extra attractions. So with a large budget, the cheapest shown package can cost a little more than that number.

## What is finished

| Feature | Status |
|---|---|
| M1–M8 (form, build, rules, day plan, total/budget/export, changes, confirm + reservation, budget too small) | Done |
| G1 changes that affect other parts (transfers swapped, missed visits removed with a reason, check-in and travel-time warnings) | Done |
| G2 price difference on every option, G3 change cities, G4 cheapest / fastest / best rated | Done |
| S1 quick request in plain words | Not done |
| S2 booking uses up seats and rooms, refuses a booking for the same last seats or rooms (`SOLD_OUT`), idempotent confirm | Done |
| S3 trip map with day routes and travel times, theme and city preferences, My bookings, modify a booked trip, photo credits | Done |

The export (section 6 format) has `trip_id` set to the reservation number after confirm (`null` before), with `status: BOOKED` and `booking.reference` on every item.

## Known limitations

- An unbooked package lives in the browser tab (`sessionStorage`). It survives a page refresh and a backend restart, but not a new tab or another device. Booked reservations are in Postgres and open from any tab by their number.
- A departure city other than the four in `destinations.json` is accepted and answered with "No flights exist from …", plus nearby options. Old names (Bangalore, Bombay, Madras, New Delhi) are mapped to their airports.
- A request with no package can take 10–25 s, because the backend builds nearby requests to suggest working alternatives.
- Travel times between places always come from the Google Routes API (see below); without Google, search answers 503 `TRAVEL_UNAVAILABLE`. Travel time is not a judged rule, so a visit added with too little time is kept, with a warning.

## Rule checks and tests

- `python backend/tests/check_trip.py trip.json`: checks an exported package against every travel rule (add `--edited` for a package the traveler changed).
- With the stack up: `cd backend && uv run pytest` runs all backend tests (they use their own database, `embark_test`). Each package the backend returns must pass the checker.
- `cd frontend && node --test src/lib/*.test.js`: frontend unit tests.

## API

The API contract (endpoints, requests, responses, errors) is in [docs/API.md](docs/API.md).

## Day plans and travel times

Each day is planned as a trip you can actually take. The traveler leaves the hotel, visits the nearest stop first, and allows travel time between stops plus 15 minutes after each visit. Every visit ends at least 30 minutes before closing, and the traveler is back at the hotel by 20:00. Arrival and city-change days get a visit only when the traveler reaches the city early enough. If a traveler adds a visit with no time to get there, the package keeps it and shows a warning. Constants are at the top of `backend/app/services/travel.py`.

Every travel time is a real road time from the Google Routes API; there is no formula estimate. Setup (required):

1. Put `GOOGLE_MAP_API=...` in the repo's `.env` (gitignored; never commit or zip it). In the key's Google Cloud project, enable the **Routes API** (travel times) and the **Maps JavaScript API** (the map).
2. `cd backend && uv run python -m app.services.travel --dry-run` shows how many elements it would request (about 2,550 for the whole catalog, billed by Google per element). Then run `uv run python -m app.services.travel --warm` once (recommended, so search rarely waits on Google).

With the key, the trip map is Google Maps in English. Without it, or if Google refuses the key, the map falls back to OpenStreetMap with English labels. The key ends up in the built frontend, as every browser Maps key does, so restrict it to your site's referrers in Google Cloud.

Results are cached in the `travel_times` table. Search reads that table and fetches any missing pair from Google on the spot, saving it for next time. If Google cannot answer (no key, network down, no route), search fails with 503 `TRAVEL_UNAVAILABLE` rather than guessing. In the UI, each leg has a "Directions" link to Google Maps.

## Database

`db/01_schema.sql` (tables, one column per field) and `db/02_seed.sql` (loads `data/catalog/*.json`) run when the Postgres volume is first created. Catalog tables have the same names as the catalog files. After a schema change, recreate the volume: `docker compose down -v && docker compose up -d` (this deletes saved bookings).
