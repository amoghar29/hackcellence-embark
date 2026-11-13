# Build My Holiday: API spec

Backend: FastAPI at `http://localhost:8000`. All bodies are JSON. All prices are whole INR. All times are **local time of the place** (`YYYY-MM-DDTHH:MM`, no offset); dates are `YYYY-MM-DD`.

**Phase 1** endpoints are fixed and covered by `backend/tests/test_api.py`. **Phase 2** (changing a package) is planned; its shapes may still change.

## Endpoints at a glance

| Group | Method and path | Purpose | Phase |
|---|---|---|---|
| Form | `GET /api/options` | Dropdown values and limits for the request form | 1 |
| **1. Search** | `POST /api/packages/search` | Build a package from the request and save it | 1 |
| | `GET /api/packages/{trip_id}` | Reopen a saved package (page refresh) | 1 |
| | `GET /api/packages/{trip_id}/export` | Download the package as the judges' JSON file | 1 |
| **2. Book** | `POST /api/packages/{trip_id}/book` | Confirm; returns the 10-digit reservation number | 1 |
| | `GET /api/reservations/{reference}` | Open a reservation by its number | 1 |
| **3. Parts** | `GET /api/packages/{trip_id}/flights` | The package's flights | 1 |
| | `GET /api/packages/{trip_id}/hotels` | The package's hotels | 1 |
| | `GET /api/packages/{trip_id}/transfers` | The package's transfers | 1 |
| | `GET /api/packages/{trip_id}/attractions` | The package's attractions | 1 |
| | `GET /api/packages/{trip_id}/days` | Day-by-day plan | 1 |
| **3. Details** | `GET /api/hotels/{hotel_id}` | Full hotel record and all its room types | 1 |
| | `GET /api/flights/{flight_id}` | Full flight record | 1 |
| | `GET /api/transfers/{transfer_id}` | Full transfer record | 1 |
| | `GET /api/attractions/{attraction_id}` | Full attraction record | 1 |
| Media | `GET /api/credits` | Photo credits (show them whenever photos are shown) | 1 |
| | `GET /images/...` | Hotel and attraction photos | 1 |
| Change | `GET /api/packages/{trip_id}/options/{hotels,flights,attractions}` | Alternatives, with price difference | 2 |
| | `PATCH /api/packages/{trip_id}` | Apply one change, or refuse with the reason | 2 |

How the parts and details fit: a package item has a short `details` summary for its card and a `catalog_id`. When the traveler opens the card, call the detail endpoint with that id, for example `GET /api/hotels/HTL-TYO-004` for the hotel item with `catalog_id: "HTL-TYO-004"`.

## Errors

Every error has the same shape, so the UI can show `error` and highlight `field`:

```json
{ "code": "INVALID_REQUEST", "error": "Nights must be between 3 and 10.", "field": "nights" }
```

| HTTP | `code` | When | Extra fields |
|---|---|---|---|
| 400 | `INVALID_REQUEST` | A request value is missing or not valid | `field`: the request field to highlight |
| 404 | `NOT_FOUND` | Unknown id or reservation number. `error` contains "not found" | |
| 422 | `NO_PACKAGE` | The request is valid but no package can be built | `reasons`, `blockers`, `suggestion`, `alternatives` |
| 422 | `OVER_BUDGET` | Packages exist but none fits the budget | `budget_inr`, `cheapest_total_inr`, `over_by_inr`, `suggestion`, `alternatives` |
| 422 | `CHANGE_REFUSED` | Phase 2: the change would break a travel rule | `reasons`, `blockers` |
| 409 | `ALREADY_BOOKED` | Phase 2: changing a booked package | |

### Reasons and recommendations (422)

Every 422 says **why** and **what to do next**:

| Field | Type | Meaning |
|---|---|---|
| `error` | string | The main reason, ready to show |
| `reasons` | list of strings | All reasons, most important first (at most 5) |
| `blockers` | list | The same reasons for code: `{ "code", "part", "message" }`. `part` is `flight`, `hotel`, `transfer` or `attraction`, so the UI can mark that part |
| `suggestion` | string | What the traveler can change, as one sentence. Never empty |
| `alternatives` | list | Request changes that the backend has already built and that work: `{ "change": { ...request fields }, "total_inr" }`. Can be empty |

To offer an alternative as a "try this" button, send the search again with `{ ...request, ...alternative.change }`. An alternative always returns 201 with the other request fields unchanged, including the budget.

How alternatives are found: the backend builds the package again for nearby requests and keeps the ones that work.

- `NO_PACKAGE`: start date up to 3 days earlier or later, then 1 night fewer or more, then the other departure cities.
- `OVER_BUDGET`: the budget raised to `cheapest_total_inr`, and fewer nights (down to 3) that fit the current budget.

When nothing nearby works, `alternatives` is `[]` and `suggestion` names the limit, for example "No flight on these dates has 10 free seats. Travel in a smaller group."

#### Blocker codes

A blocker stops one city plan. The response lists blockers only when **every** city plan is blocked; blockers common to all plans come first.

| `code` | `part` | When | Example `message` |
|---|---|---|---|
| `NO_ARRIVAL_FLIGHT` | `flight` | No flight from the departure city lands on the start date at an airport that serves the first city | "No flight from BOM lands in Japan on 2027-04-03." |
| `ARRIVAL_SEATS` | `flight` | Flights land that day, but none has a seat for every traveler | "Flights from BLR to Japan on 2027-04-10 have at most 9 free seats; you need 10." |
| `NO_RETURN_FLIGHT` | `flight` | No flight to the departure city leaves on the last day from an airport that serves the last city | "No flight from Japan to BOM leaves on 2027-04-08." |
| `RETURN_SEATS` | `flight` | Return flights leave that day, but none has a seat for every traveler | "Flights from Japan to BLR on 2027-04-16 have at most 2 free seats; you need 3." |
| `NO_ROOM_FITS` | `hotel` | No room type in the city fits the travelers (each room needs an adult) | "No room type in Kyoto fits 1 adult and 6 children." |
| `HOTEL_SOLD_OUT` | `hotel` | Room types fit, but none has enough rooms left on every night of the stay | "No hotel in Kyoto has 2 rooms free on every night from 2027-04-13 to 2027-04-16." |
| `NO_AIRPORT_TRANSFER` | `transfer` | No airport transfer serves the city and area of any hotel that can be booked | "No transfer from AUH serves the available hotels in Abu Dhabi." |
| `ARRIVAL_TOO_LATE` | `transfer` | Every arrival flight lands when no airport transfer is in service | "The flight lands at 23:40; airport transfers from KIX stop at 23:00." |
| `RETURN_TOO_EARLY` | `transfer` | Every return flight leaves too early to reach the airport 180 minutes before, on the last day | "The return flight leaves at 02:10; no transfer reaches DXB by 23:10." |
| `NO_INTERCITY` | `transfer` | No transfer between two cities of the plan runs on the city-change day | "No transfer from Dubai to Abu Dhabi runs on 2027-04-08." |
| `NOT_ENOUGH_ATTRACTIONS` | `attraction` | A full day has no open attraction left in that city | "Abu Dhabi has no open attraction left for 2027-04-15." |

A refused change (Phase 2) uses the same codes where they apply, for example `HOTEL_SOLD_OUT` for a hotel with no rooms on the stay's nights.

---

## Form

### `GET /api/options`

```json
{
  "departure_cities": [
    { "airport": "BLR", "city": "Bengaluru" },
    { "airport": "DEL", "city": "Delhi" },
    { "airport": "BOM", "city": "Mumbai" },
    { "airport": "MAA", "city": "Chennai" }
  ],
  "countries": ["Japan", "United Arab Emirates"],
  "rules": {
    "min_nights": 3, "max_nights": 10, "min_nights_per_city": 2,
    "first_night": "2027-04-01", "last_departure": "2027-04-20"
  }
}
```

Use `rules` for the date picker and the nights input: the start date must be on or after `first_night`, and start date + nights must be on or before `last_departure`.

---

## 1. Search

### `POST /api/packages/search`

Request (the 7 form fields):

```json
{
  "departure_city": "BLR",
  "country": "Japan",
  "start_date": "2027-04-10",
  "nights": 6,
  "adults": 2,
  "child_ages": [6],
  "budget_inr": 350000
}
```

| Field | Rule | Accepted forms |
|---|---|---|
| `departure_city` | One of the 4 departure cities | Airport code or city name, any case (`"BLR"`, `"bengaluru"`) |
| `country` | `Japan` or `United Arab Emirates` | Any case; extra spaces ignored |
| `start_date` | First day in the destination (the arrival flight lands that day) | `YYYY-MM-DD` |
| `nights` | 3 to 10; `start_date + nights` (the return day) on or before 20 April 2027 | Integer |
| `adults` | 1 or more | Integer |
| `child_ages` | One age per child, each 0 to 17. Optional, defaults to `[]` | List of integers |
| `budget_inr` | More than 0 | Integer, or text such as `"3,50,000"` |

Responses:

- **201**: a [Package](#the-package-object), saved with `status: "PLANNED"`. The app chooses the cities and builds the cheapest package that passes every travel rule. The first package has one attraction on each full day, and none on the arrival day, on city-change days and on the last day.
- **400** `INVALID_REQUEST`: the message says how to fix the value, for example `{"code": "INVALID_REQUEST", "error": "The trip must end by 2027-04-20. Start on or before 2027-04-15, or choose fewer nights.", "field": "start_date"}`.
- **422** `NO_PACKAGE` (see [Reasons and recommendations](#reasons-and-recommendations-422)):
  ```json
  { "code": "NO_PACKAGE",
    "error": "No flight from BOM lands in Japan on 2027-04-03.",
    "reasons": ["No flight from BOM lands in Japan on 2027-04-03."],
    "blockers": [
      { "code": "NO_ARRIVAL_FLIGHT", "part": "flight", "message": "No flight from BOM lands in Japan on 2027-04-03." }
    ],
    "suggestion": "A package is possible if you start on 2027-04-04, or fly from Delhi.",
    "alternatives": [
      { "change": { "start_date": "2027-04-04" }, "total_inr": 251200 },
      { "change": { "departure_city": "DEL" }, "total_inr": 263900 }
    ] }
  ```
- **422** `OVER_BUDGET`:
  ```json
  { "code": "OVER_BUDGET", "error": "No package fits a budget of ₹10,000.",
    "budget_inr": 10000, "cheapest_total_inr": 266378, "over_by_inr": 256378,
    "suggestion": "Raise the budget to ₹2,66,378.",
    "alternatives": [
      { "change": { "budget_inr": 266378 }, "total_inr": 266378 }
    ] }
  ```
  When fewer nights fit the current budget, that is offered too: `"suggestion": "Raise the budget to ₹2,66,378, or take 4 nights (₹1,98,400)."` with `{ "change": { "nights": 4 }, "total_inr": 198400 }` in `alternatives`.

### `GET /api/packages/{trip_id}`

**200**: the [Package](#the-package-object). **404** `NOT_FOUND`. Keep `trip_id` in the URL (for example `#/package/{trip_id}`) so a page refresh reopens it.

### `GET /api/packages/{trip_id}/export`

**200**: the shared trip format file (`Content-Disposition: attachment; filename="trip-{trip_id}.json"`). Same top-level fields and items as the Package, without the UI-only fields (`nights`, `cities`, `remaining_inr`, `days`, item `details`). Use a plain link or `<a download>`.

---

## 2. Book

### `POST /api/packages/{trip_id}/book`

No body. **200**:

```json
{ "reference": "4829105736", "package": { "...": "Package with status BOOKED" } }
```

After booking, the package and every item have `status: "BOOKED"`, and every item has `booking: {"reference": "4829105736"}`. Booking again returns the same reference. **404** `NOT_FOUND`.

### `GET /api/reservations/{reference}`

**200**: the booked [Package](#the-package-object). **404** `NOT_FOUND` for an unknown or malformed number; show "Reservation not found". Works after a backend restart.

---

## 3. Parts of a package

All return **200** `{ "trip_id": "...", "items": [ ... ] }` with the package's items of that type, ordered by `start`, in the same [Item](#item) shape as in the Package. **404** `NOT_FOUND` for an unknown `trip_id`.

- `GET /api/packages/{trip_id}/flights`
- `GET /api/packages/{trip_id}/hotels`
- `GET /api/packages/{trip_id}/transfers`
- `GET /api/packages/{trip_id}/attractions`

`GET /api/packages/{trip_id}/days` returns **200** `{ "trip_id": "...", "days": [ ... ] }` (see [Day-by-day plan](#day-by-day-plan-days)).

## 3. Details from the catalog

Read-only. **404** `NOT_FOUND` for an unknown id. Image paths are served by the backend (see [Images](#images)).

### `GET /api/hotels/{hotel_id}`

```json
{
  "hotel_id": "HTL-TYO-004", "name": "Ueno Garden Inn", "city": "Tokyo", "area": "Ueno",
  "stars": 3, "rating": 7.9, "check_in_from": "15:00", "check_out_until": "11:00",
  "family_friendly": true, "lat": 35.712, "lng": 139.7728, "image": "/images/hotels/HOTEL-BUSINESS-1.jpg",
  "rooms": [
    { "room_id": "RM-TYO-004-A", "room_type": "TWIN", "name": "Twin Room",
      "max_adults": 2, "max_children": 0, "price_per_night_inr": 7000, "refundable": true },
    { "room_id": "RM-TYO-004-B", "room_type": "FAMILY", "name": "Family Room",
      "max_adults": 2, "max_children": 2, "price_per_night_inr": 9464, "refundable": false }
  ]
}
```

### `GET /api/flights/{flight_id}`

`flight_id`, `airline`, `flight_number`, `from_airport`, `from_airport_name`, `to_airport`, `to_airport_name`, `departure_local`, `arrival_local`, `stops`, `duration_minutes`, `price_per_seat_inr`, `seats_left`, `cabin`.

### `GET /api/transfers/{transfer_id}`

`transfer_id`, `type`, `name`, `airport`, `city`, `area`, `from_city`, `to_city`, `from_point`, `to_point`, `door_to_door`, `max_passengers`, `service_from`, `service_until`, `frequency_minutes`, `duration_minutes`, `pricing`, `price_inr`, `child_price_inr`. Fields that do not apply are `null`.

### `GET /api/attractions/{attraction_id}`

`attraction_id`, `name`, `name_ja`, `aliases`, `city`, `category`, `open_days`, `open_from`, `open_until`, `closed_dates` (list, may be empty), `visit_minutes`, `child_friendly`, `accessible`, `price_per_person_inr`, `child_price_inr` (`null` = children pay the adult price; `0` = free for children), `lat`, `lng`, `image`.

---

## Media

### `GET /api/credits`

**200** `{ "markdown": "..." }`: the photo credits from `images/ATTRIBUTIONS.md`. Show them on a credits link or in the footer whenever photos are shown.

### Images

`image` fields are paths such as `/images/attractions/ATT-KYO-001.jpg`. Load them from the backend: `http://localhost:8000/images/attractions/ATT-KYO-001.jpg`.

---

## The Package object

Top-level fields are the judges' trip format plus some fields for the UI (marked UI).

| Field | Type | Meaning |
|---|---|---|
| `trip_id` | string | Package ID |
| `status` | `PLANNED` \| `BOOKED` | |
| `reference` | string \| null | 10-digit reservation number after booking |
| `traveler` | object | `{ "name": null, "home_airport": "BLR", "adults": 2, "children": 1, "child_ages": [6] }` |
| `country` | string | `Japan` |
| `start_date`, `end_date` | date | Arrival day, return day |
| `nights` | int | UI |
| `cities` | list | UI. City plan in order: `{ "city", "nights", "check_in", "check_out" }` |
| `budget_inr`, `total_inr` | int | |
| `remaining_inr` | int | UI. `budget_inr - total_inr`; negative = over budget |
| `items` | list | Flights, hotels, transfers, attractions (below), ordered by `start` |
| `days` | list | UI. Day-by-day plan (below) |

### Item

```json
{
  "item_id": "i3",
  "type": "hotel",
  "name": "Ueno Garden Inn",
  "city": "Tokyo",
  "status": "PLANNED",
  "catalog_id": "HTL-TYO-004",
  "room_id": "RM-TYO-004-B",
  "start": "2027-04-10",
  "end": "2027-04-13",
  "quantity": 1,
  "price_inr": 28392,
  "booking": null,
  "sources": [],
  "warnings": [],
  "details": { "...": "see below" }
}
```

| Type | `start` / `end` | `quantity` | `city` |
|---|---|---|---|
| `flight` | Departure / arrival date-time | Seats | Arrival city (`Bengaluru` for the return flight) |
| `hotel` | Check-in / check-out date | Rooms | Hotel city |
| `transfer` | Pickup / arrival date-time | Vehicles (taxi, van) or tickets (bus, train) | Destination city of the ride |
| `attraction` | Visit start / end date-time | Tickets | Attraction city |

`room_id` is set on hotel items only (`null` on the others).

`details` (UI only, a summary for the card; the full record is on the [detail endpoints](#3-details-from-the-catalog)):

| Type | `details` fields |
|---|---|
| `flight` | `direction` (`ARRIVAL` \| `RETURN`), `airline`, `flight_number`, `from_airport`, `to_airport`, `stops`, `duration_minutes`, `price_per_seat_inr` |
| `hotel` | `area`, `stars`, `rating`, `room_type`, `room_name`, `rooms`, `nights`, `price_per_night_inr`, `check_in_from`, `check_out_until`, `image` |
| `transfer` | `kind` (`AIRPORT_ARRIVAL` \| `AIRPORT_RETURN` \| `INTERCITY`), `transfer_type` (`AIRPORT_TAXI`, `TRAIN`, ...), `from_point`, `to_point`, `duration_minutes`, `pricing` |
| `attraction` | `category`, `visit_minutes`, `open_from`, `open_until`, `child_friendly`, `image` |

### Day-by-day plan (`days`)

One entry per calendar date, in order, with no gaps. It can start the day before `start_date` (an overnight flight from India) and end the day after `end_date` (a return flight landing after midnight).

```json
{
  "date": "2027-04-13",
  "day_type": "CITY_CHANGE",
  "city": "Kyoto",
  "events": [
    { "time": "10:00", "kind": "CHECK_OUT", "item_id": "i3", "title": "Check out: Ueno Garden Inn", "timezone": "Asia/Tokyo" },
    { "time": "10:00", "kind": "TRANSFER", "item_id": "i8", "title": "Train Tokyo to Kyoto", "timezone": "Asia/Tokyo" }
  ]
}
```

| Field | Values |
|---|---|
| `day_type` | `TRAVEL` (before `start_date`), `ARRIVAL` (`start_date`), `FULL`, `CITY_CHANGE`, `RETURN` (`end_date`), `HOME` (after `end_date`) |
| `city` | City of that night's hotel; the last city on `RETURN`; `null` on `TRAVEL` and `HOME` |
| `events` | Sorted by `time` (local time of that place) |
| `kind` | `FLIGHT_DEPARTURE`, `FLIGHT_ARRIVAL`, `TRANSFER`, `CHECK_IN`, `CHECK_OUT`, `ATTRACTION` |

Every item appears in at least one event. A hotel has a `CHECK_IN` event on its check-in date and a `CHECK_OUT` event on its check-out date. `CHECK_OUT` time is the hotel's `check_out_until`, or the time of the first pickup that day if earlier.

---

## Phase 2 (planned): changing a package

Each change is checked against every travel rule. A refused change leaves the package unchanged.

### Change options

| Call | Returns `options[]` with |
|---|---|
| `GET /api/packages/{trip_id}/options/hotels?city=Kyoto` | `hotel_id`, `room_id`, `name`, `area`, `stars`, `rating`, `room_type`, `rooms`, `price_inr`, `price_diff_inr`, `image` |
| `GET /api/packages/{trip_id}/options/flights?direction=ARRIVAL` | `flight_id`, `flight_number`, `airline`, `from_airport`, `to_airport`, `departure`, `arrival`, `stops`, `price_inr`, `price_diff_inr` |
| `GET /api/packages/{trip_id}/options/attractions?date=2027-04-12` | `attraction_id`, `name`, `category`, `start`, `end`, `price_inr`, `image` |

`price_diff_inr` = option price minus current price (negative = cheaper).

### `PATCH /api/packages/{trip_id}`

One change per call:

```json
{ "action": "change_hotel", "city": "Kyoto", "hotel_id": "HTL-KYO-005", "room_id": "RM-KYO-005-C" }
{ "action": "change_flight", "item_id": "i1", "flight_id": "FL-405" }
{ "action": "add_attraction", "attraction_id": "ATT-TYO-009", "start": "2027-04-12T16:00" }
{ "action": "remove_attraction", "item_id": "i7" }
```

**200**: the updated Package; affected items can carry `warnings`. **409** `ALREADY_BOOKED`. **422** `CHANGE_REFUSED` with `error`, `reasons` and `blockers`; the package is unchanged:

```json
{ "code": "CHANGE_REFUSED",
  "error": "Kyoto Riverside Inn has no Family Room free on 2027-04-14.",
  "reasons": ["Kyoto Riverside Inn has no Family Room free on 2027-04-14."],
  "blockers": [
    { "code": "HOTEL_SOLD_OUT", "part": "hotel", "message": "Kyoto Riverside Inn has no Family Room free on 2027-04-14." }
  ] }
```

A change that breaks a rule with no blocker code (for example two visits that overlap) has the rule's message in `reasons` and `blockers: []`.

---

## Typical frontend flow

1. Load `GET /api/options` for the form.
2. Submit `POST /api/packages/search`.
   - 201: go to `#/package/{trip_id}`.
   - 400: show `error` next to `field`.
   - 422 `NO_PACKAGE`: show `error`, `reasons` and `suggestion`. Offer each entry of `alternatives` as a button that searches again with that change.
   - 422 `OVER_BUDGET`: show the cheapest total, the gap and `suggestion`, with the same buttons for `alternatives`.
3. Package page: render `days` and the item cards; show `total_inr`, `budget_inr` and `remaining_inr`. A card click calls the detail endpoint with its `catalog_id`. Add an Export link to `/export` and a Book button.
4. Book: `POST .../book`, then go to `#/reservation/{reference}`.
5. Reservation page: `GET /api/reservations/{reference}`. On 404 show "Reservation not found".
