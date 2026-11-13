"""The package builder (app.services.builder): every package it returns passes every rule,
and when no package is possible it says why and what to change. Contract: docs/API.md.

  builder.city_plans(country, nights, cat) -> list of plans; a plan is [(city, nights), ...]
  builder.build(request, cat) -> trip (shared trip format), the cheapest package that passes validator.validate
      request = the normalized dict from request_form.validate_request
  raises builder.NoPackage   .blockers [{code, part, message}], .reasons, .suggestion, .alternatives
  raises builder.OverBudget  .cheapest_total_inr, .suggestion, .alternatives
      alternatives = [{"change": {request fields}, "total_inr": n}], each one already built

Blocker tests doctor the catalog tables inside the test's transaction (rolled back afterwards), so each
blocker is hit on purpose and no test depends on finding a lucky real request.
"""
from datetime import date, datetime, timedelta

import pytest

from app.repositories.catalog_repo import CatalogRepository
from app.services import builder, validator
from app.services.request_form import validate_request
from tests.check_trip import check, load_catalog
from tests.conftest import MENON_REQUEST

J = load_catalog()  # the JSON catalog, independent of the app
HUGE = 100_000_000
START, END = date(2027, 4, 10), date(2027, 4, 16)  # the Menon trip


def raw(**changes):
    return dict(MENON_REQUEST, **changes)


def req(cat, **changes):
    return validate_request(raw(**changes), cat)


def codes(exc):
    return [b["code"] for b in exc.blockers]


def no_package(cat, **changes):
    with pytest.raises(builder.NoPackage) as e:
        builder.build(req(cat, **changes), cat)
    exc = e.value
    assert exc.blockers and exc.reasons == [b["message"] for b in exc.blockers]
    assert all(b["part"] in {"flight", "hotel", "transfer", "attraction"} and b["message"].strip()
               for b in exc.blockers)
    assert exc.suggestion.strip()
    return exc


def of_type(trip, type_):
    return [i for i in trip["items"] if i["type"] == type_]


# ---------- doctoring the catalog ----------

def doctor(cat, table, key, change):
    """change(row) -> row, or None to delete it. Returns a repository that sees the changed table."""
    conn = cat.conn
    conn.execute("DELETE FROM bookings")  # saved packages reference catalog rows
    for row in conn.execute(f"SELECT * FROM {table}").fetchall():
        new = change(dict(row))
        if new is None:
            conn.execute(f"DELETE FROM {table} WHERE {key} = %s", (row[key],))
        elif new != row:
            cols = [c for c in new if new[c] != row[c]]
            conn.execute(f"UPDATE {table} SET {', '.join(f'{c} = %s' for c in cols)} WHERE {key} = %s",
                         [new[c] for c in cols] + [row[key]])
    return CatalogRepository(conn)


def with_flights(cat, change):
    """change(flight) -> flight, or None to remove it."""
    return doctor(cat, "flights", "flight_id", change)


def lands_on(day, home="BLR"):
    return lambda f: f["from_airport"] == home and f["arrival_local"].date() == day


def leaves_on(day, home="BLR"):
    return lambda f: f["to_airport"] == home and f["departure_local"].date() == day


def sold_out(cat, when):
    """when(room_id, night) -> True to set rooms_left to 0."""
    hit = [r for r in cat.conn.execute("SELECT room_id, date FROM availability").fetchall() if when(r["room_id"], r["date"])]
    cat.conn.execute("UPDATE availability SET rooms_left = 0 WHERE (room_id, date) IN "
                     "(SELECT * FROM unnest(%s::text[], %s::date[]))",
                     ([r["room_id"] for r in hit], [r["date"] for r in hit]))
    return CatalogRepository(cat.conn)


def city_of_room(cat, room_id):
    return cat.get_hotel(cat.get_room(room_id)["hotel_id"])["city"]


# ---------- city plans ----------

@pytest.mark.parametrize("country", ["Japan", "United Arab Emirates"])
@pytest.mark.parametrize("nights", range(3, 11))
def test_city_plans_follow_the_city_rules(cat, country, nights):
    plans = builder.city_plans(country, nights, cat)
    assert plans
    assert len({tuple(p) for p in plans}) == len(plans)
    c = next(c for c in cat.destinations["countries"] if c["name"] == country)
    names = {x["name"] for x in c["cities"]}
    links = {(link["from_city"], link["to_city"]) for link in c["links"]}
    for plan in plans:
        cities = [city for city, _ in plan]
        assert sum(n for _, n in plan) == nights
        assert all(n >= 2 for _, n in plan)
        assert len(set(cities)) == len(cities) and set(cities) <= names
        assert all(pair in links for pair in zip(cities, cities[1:]))


@pytest.mark.parametrize("country,cities", [("Japan", 3), ("United Arab Emirates", 2)])
def test_three_nights_is_always_one_city(cat, country, cities):
    plans = builder.city_plans(country, 3, cat)
    assert len(plans) == cities and all(len(p) == 1 for p in plans)


def test_every_split_of_the_nights_is_a_plan(cat):
    assert len(builder.city_plans("Japan", 4, cat)) == 3 + 6          # 3 single cities + 6 ordered pairs (2+2)
    assert len(builder.city_plans("United Arab Emirates", 5, cat)) == 2 + 2 * 2  # pairs split 2+3 and 3+2


# ---------- a correct package ----------

BUILDS = {
    "menon": {},
    "uae_from_delhi": dict(departure_city="DEL", country="United Arab Emirates", start_date="2027-04-05", nights=4,
                           child_ages=[], budget_inr=300000),
    "one_city_japan": dict(departure_city="DEL", start_date="2027-04-01", nights=3, adults=1, child_ages=[],
                           budget_inr=300000),
    "one_city_uae": dict(departure_city="DEL", country="United Arab Emirates", start_date="2027-04-05", nights=3,
                         child_ages=[], budget_inr=300000),
    "ten_nights": dict(nights=10, child_ages=[], budget_inr=1000000),
    "big_family": dict(country="United Arab Emirates", start_date="2027-04-12", adults=4, child_ages=[0, 12],
                       budget_inr=1000000),
}


@pytest.mark.parametrize("changes", BUILDS.values(), ids=BUILDS.keys())
def test_package_passes_both_checkers(cat, changes):
    r = req(cat, **changes)
    trip = builder.build(r, cat)
    assert validator.validate(trip, cat) == []
    assert check(trip, J) == []
    assert trip["total_inr"] <= r["budget_inr"]
    assert (trip["start_date"], trip["end_date"]) == (r["start_date"].isoformat(), r["end_date"].isoformat())


@pytest.mark.parametrize("name", ["one_city_japan", "one_city_uae"])
def test_one_city_trip_has_no_transfer_between_cities(cat, name):
    trip = builder.build(req(cat, **BUILDS[name]), cat)
    assert len(of_type(trip, "hotel")) == 1
    assert [J["transfers"][t["catalog_id"]].get("airport") is not None for t in of_type(trip, "transfer")] == [True, True]


@pytest.mark.parametrize("changes", BUILDS.values(), ids=BUILDS.keys())
def test_first_package_has_one_attraction_on_each_full_day_only(cat, changes):
    trip = builder.build(req(cat, **changes), cat)
    start, end = date.fromisoformat(trip["start_date"]), date.fromisoformat(trip["end_date"])
    change_days = {date.fromisoformat(h["start"]) for h in of_type(trip, "hotel")} - {start}
    full_days = {start + timedelta(n) for n in range(1, (end - start).days)} - change_days
    visits = [datetime.fromisoformat(a["start"]).date() for a in of_type(trip, "attraction")]
    assert sorted(visits) == sorted(full_days)


@pytest.mark.parametrize("changes", BUILDS.values(), ids=BUILDS.keys())
def test_airport_transfer_times(cat, changes):
    trip = builder.build(req(cat, **changes), cat)
    arrival, ret = sorted((t for t in of_type(trip, "transfer") if J["transfers"][t["catalog_id"]].get("airport")),
                          key=lambda t: t["start"])
    home = trip["traveler"]["home_airport"]
    out = next(f for f in of_type(trip, "flight") if J["flights"][f["catalog_id"]]["from"] == home)
    back = next(f for f in of_type(trip, "flight") if J["flights"][f["catalog_id"]]["to"] == home)
    at = datetime.fromisoformat
    assert at(arrival["start"]) >= at(out["end"]) + timedelta(minutes=60)
    assert ret["start"][:10] == trip["end_date"]  # leaves the hotel on the last day, not the evening before
    assert at(ret["end"]) <= at(back["start"]) - timedelta(minutes=180)


def test_same_request_gives_the_same_package(cat):
    first, second = builder.build(req(cat), cat), builder.build(req(cat), cat)
    assert first["items"] == second["items"] and first["total_inr"] == second["total_inr"]


def test_one_stop_flight_is_used_when_it_is_the_only_option(cat):
    # FL-405 BLR->NRT is the only one-stop flight landing on 04-10 (21:30); remove the direct ones
    late = with_flights(cat, lambda f: None if lands_on(START)(f) and f["stops"] == 0 else f)
    trip = builder.build(req(late), late)
    assert "FL-405" in [f["catalog_id"] for f in of_type(trip, "flight")]
    assert validator.validate(trip, late) == []
    assert check(trip, J) == []


# ---------- the gate: nothing leaves the builder without passing the validator ----------

def test_package_that_fails_the_validator_is_never_returned(cat, monkeypatch):
    monkeypatch.setattr(validator, "validate", lambda *a, **k: ["PRICE: forced by the test"])
    with pytest.raises(builder.NoPackage):
        builder.build(req(cat), cat)


# ---------- blockers: why no package is possible ----------

def test_too_many_travelers_for_any_flight(cat):
    exc = no_package(cat, adults=8, child_ages=[5, 7], budget_inr=HUGE)  # 10 travelers, max seats_left is 9
    assert codes(exc)[0] == "ARRIVAL_SEATS"
    assert "10" in exc.reasons[0]


def test_no_arrival_flight_that_day(cat):
    c = with_flights(cat, lambda f: None if lands_on(START)(f) else f)
    exc = no_package(c)
    assert codes(exc)[0] == "NO_ARRIVAL_FLIGHT"
    assert "2027-04-10" in exc.reasons[0] and "BLR" in exc.reasons[0]


def test_no_return_flight_that_day(cat):
    c = with_flights(cat, lambda f: None if leaves_on(END)(f) else f)
    exc = no_package(c)
    assert codes(exc)[0] == "NO_RETURN_FLIGHT"
    assert "2027-04-16" in exc.reasons[0]


def test_return_flights_without_enough_seats(cat):
    c = with_flights(cat, lambda f: dict(f, seats_left=1) if leaves_on(END)(f) else f)
    assert codes(no_package(c))[0] == "RETURN_SEATS"


def test_no_room_type_fits_the_group(cat):
    # 1 adult + 6 children: the largest room holds 6 and every room needs an adult
    c = with_flights(cat, lambda f: dict(f, seats_left=9))
    exc = no_package(c, adults=1, child_ages=[5] * 6, budget_inr=HUGE)
    assert "NO_ROOM_FITS" in codes(exc)


def test_hotels_sold_out_on_one_night(cat):
    c = sold_out(cat, lambda room_id, night: night == date(2027, 4, 12))
    exc = no_package(c)
    assert "HOTEL_SOLD_OUT" in codes(exc)
    assert any("2027-04-12" in b["message"] for b in exc.blockers if b["code"] == "HOTEL_SOLD_OUT")


def test_arrival_after_the_last_airport_transfer(cat):
    c = with_flights(cat, lambda f: dict(f, arrival_local=datetime(2027, 4, 10, 23, 40)) if lands_on(START)(f) else f)
    c = doctor(c, "transfers", "transfer_id",
               lambda t: dict(t, service_from="06:00", service_until="23:00") if t["airport"] else t)
    assert "ARRIVAL_TOO_LATE" in codes(no_package(c))


def test_return_flight_too_early_to_reach_the_airport(cat):
    c = with_flights(cat, lambda f: dict(f, departure_local=datetime(2027, 4, 16, 2, 10)) if leaves_on(END)(f) else f)
    assert "RETURN_TOO_EARLY" in codes(no_package(c))


def test_not_enough_attractions_for_the_full_days(cat):
    one_per_city = {}
    for a in cat.list_attractions():
        one_per_city.setdefault(a["city"], a)
    keep = {a["attraction_id"] for a in one_per_city.values()}
    c = doctor(cat, "attractions", "attraction_id", lambda a: a if a["attraction_id"] in keep else None)
    exc = no_package(c, nights=10, child_ages=[], budget_inr=HUGE)  # at least 7 full days, 3 attractions
    assert "NOT_ENOUGH_ATTRACTIONS" in codes(exc)


def test_a_blocked_city_does_not_block_the_request(cat):
    c = sold_out(cat, lambda room_id, night: city_of_room(cat, room_id) == "Kyoto")
    trip = builder.build(req(c), c)
    assert "Kyoto" not in [h["city"] for h in of_type(trip, "hotel")]
    assert validator.validate(trip, c) == []


def test_blocker_common_to_every_plan_comes_first(cat):
    c = sold_out(cat, lambda room_id, night: city_of_room(cat, room_id) == "Kyoto")
    exc = no_package(c, adults=8, child_ages=[5, 7], budget_inr=HUGE)
    assert codes(exc)[0] == "ARRIVAL_SEATS"


def test_at_most_five_reasons(cat):
    c = sold_out(cat, lambda room_id, night: True)
    assert len(no_package(c).blockers) <= 5


# ---------- budget ----------

def cheapest_menon(cat):
    return builder.build(req(cat, budget_inr=HUGE), cat)["total_inr"]


def test_budget_equal_to_the_cheapest_total_is_enough(cat):
    cheapest = cheapest_menon(cat)
    assert builder.build(req(cat, budget_inr=cheapest), cat)["total_inr"] == cheapest


def test_budget_one_rupee_short(cat):
    cheapest = cheapest_menon(cat)
    with pytest.raises(builder.OverBudget) as e:
        builder.build(req(cat, budget_inr=cheapest - 1), cat)
    assert e.value.cheapest_total_inr == cheapest
    assert e.value.suggestion.strip()
    assert {"change": {"budget_inr": cheapest}, "total_inr": cheapest} in e.value.alternatives


def test_over_budget_is_not_no_package(cat):
    with pytest.raises(builder.OverBudget):
        builder.build(req(cat, budget_inr=10000), cat)


# ---------- recommendations: every alternative was really built ----------

def assert_alternatives_build(cat, original, alternatives):
    for alt in alternatives:
        assert alt["change"] and set(alt["change"]) <= set(original)
        r = validate_request(dict(original, **alt["change"]), cat)
        trip = builder.build(r, cat)
        assert trip["total_inr"] == alt["total_inr"] <= r["budget_inr"]
        assert validator.validate(trip, cat) == []


def test_no_package_alternatives_build(cat):
    c = with_flights(cat, lambda f: None if lands_on(START)(f) else f)
    exc = no_package(c)
    assert exc.alternatives  # other start dates and other departure cities still work
    assert_alternatives_build(c, raw(), exc.alternatives)


def test_over_budget_alternatives_build(cat):
    cheapest = cheapest_menon(cat)
    with pytest.raises(builder.OverBudget) as e:
        builder.build(req(cat, budget_inr=cheapest - 1), cat)
    assert_alternatives_build(cat, raw(budget_inr=cheapest - 1), e.value.alternatives)


def test_no_alternative_when_nothing_nearby_works(cat):
    exc = no_package(cat, adults=8, child_ages=[5, 7], budget_inr=HUGE)  # no flight seats 10 on any date
    assert exc.alternatives == []
    assert exc.suggestion.strip()
