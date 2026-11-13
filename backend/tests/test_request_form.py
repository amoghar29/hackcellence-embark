"""Request form (M1): validation and normalization of the 7 request fields.

Contract:
  app.services.request_form.validate_request(raw: dict, cat) -> dict
      normalized: departure_city (airport code), country (catalog name), start_date (date),
                  end_date (date = start + nights, the return-flight day), nights, adults,
                  child_ages (list[int]), budget_inr
  raises app.services.request_form.InvalidRequest(ValueError) with
      .field = the offending request field, str(exc) = a clear, non-empty message
  GET /api/options -> 200 {"departure_cities": [{"airport", "city"}], "countries": [names]}
"""
from datetime import date

import pytest

from app.services.request_form import InvalidRequest, validate_request

VALID = {
    "departure_city": "BLR",
    "country": "Japan",
    "start_date": "2027-04-10",
    "nights": 6,
    "adults": 2,
    "child_ages": [6],
    "budget_inr": 350000,
}


def ok(cat, **changes):
    return validate_request(dict(VALID, **changes), cat)


def rejected(cat, field, raw):
    with pytest.raises(InvalidRequest) as e:
        validate_request(raw, cat)
    assert e.value.field == field
    assert str(e.value).strip()


# ---------- valid input ----------

def test_menon_request_is_valid(cat):
    assert validate_request(dict(VALID), cat) == {
        "departure_city": "BLR",
        "country": "Japan",
        "start_date": date(2027, 4, 10),
        "end_date": date(2027, 4, 16),
        "nights": 6,
        "adults": 2,
        "child_ages": [6],
        "budget_inr": 350000,
    }


def test_input_is_not_mutated(cat):
    raw = dict(VALID, child_ages=["6"], nights="6")
    validate_request(raw, cat)
    assert raw["child_ages"] == ["6"] and raw["nights"] == "6"


@pytest.mark.parametrize("airport", ["BLR", "DEL", "BOM", "MAA"])
def test_every_departure_city_accepted(cat, airport):
    assert ok(cat, departure_city=airport)["departure_city"] == airport


@pytest.mark.parametrize("country", ["Japan", "United Arab Emirates"])
def test_every_country_accepted(cat, country):
    assert ok(cat, country=country)["country"] == country


def test_no_children(cat):
    assert ok(cat, child_ages=[])["child_ages"] == []


@pytest.mark.parametrize("missing", [None, "absent"])
def test_child_ages_optional(cat, missing):
    raw = dict(VALID, child_ages=None)
    if missing == "absent":
        del raw["child_ages"]
    assert validate_request(raw, cat)["child_ages"] == []


@pytest.mark.parametrize("age", [0, 17])
def test_child_age_bounds_inclusive(cat, age):
    assert ok(cat, child_ages=[age])["child_ages"] == [age]


def test_several_children_keep_order(cat):
    assert ok(cat, adults=2, child_ages=[12, 0, 5])["child_ages"] == [12, 0, 5]


def test_single_adult(cat):
    assert ok(cat, adults=1, child_ages=[])["adults"] == 1


@pytest.mark.parametrize("nights", [3, 10])
def test_nights_bounds_inclusive(cat, nights):
    assert ok(cat, nights=nights)["nights"] == nights


# ---------- dates: return (end) after start, inside the data window ----------

def test_end_date_is_start_plus_nights(cat):
    r = ok(cat, start_date="2027-04-05", nights=4)
    assert r["end_date"] == date(2027, 4, 9)
    assert r["end_date"] > r["start_date"]


@pytest.mark.parametrize("start,nights", [
    ("2027-04-01", 3),   # first allowed night
    ("2027-04-10", 10),  # returns exactly on 20 April
    ("2027-04-17", 3),   # latest start that still returns by 20 April
])
def test_window_boundaries_accepted(cat, start, nights):
    assert ok(cat, start_date=start, nights=nights)["end_date"] <= date(2027, 4, 20)


@pytest.mark.parametrize("start,nights", [
    ("2027-03-31", 3),   # first night before 1 April
    ("2027-04-18", 3),   # returns 21 April
    ("2027-04-11", 10),  # returns 21 April
    ("2027-04-20", 3),   # starts on the last departure day
    ("2026-04-10", 6),   # right month, wrong year
])
def test_dates_outside_window_rejected(cat, start, nights):
    rejected(cat, "start_date", dict(VALID, start_date=start, nights=nights))


# ---------- normalization ----------

@pytest.mark.parametrize("given", ["blr", " BLR ", "Bengaluru", "bengaluru ", "BENGALURU"])
def test_departure_city_normalized_to_airport(cat, given):
    assert ok(cat, departure_city=given)["departure_city"] == "BLR"


@pytest.mark.parametrize("given,expected", [
    ("japan", "Japan"),
    ("  JAPAN ", "Japan"),
    ("united arab emirates", "United Arab Emirates"),
    (" United  Arab Emirates", "United Arab Emirates"),
])
def test_country_normalized_to_catalog_name(cat, given, expected):
    assert ok(cat, country=given)["country"] == expected


def test_start_date_whitespace_stripped(cat):
    assert ok(cat, start_date=" 2027-04-10 ")["start_date"] == date(2027, 4, 10)


def test_numeric_strings_become_ints(cat):
    r = ok(cat, nights="6", adults=" 2 ", child_ages=["6", 9], budget_inr="350000")
    assert (r["nights"], r["adults"], r["child_ages"], r["budget_inr"]) == (6, 2, [6, 9], 350000)
    assert all(type(x) is int for x in (r["nights"], r["adults"], *r["child_ages"]))


def test_whole_number_floats_accepted(cat):
    r = ok(cat, nights=6.0, adults=2.0, child_ages=[6.0])
    assert (r["nights"], r["adults"], r["child_ages"]) == (6, 2, [6])


@pytest.mark.parametrize("given", ["3,50,000", "350,000", " 350000 ", 350000.0])
def test_budget_formats_normalized(cat, given):
    assert ok(cat, budget_inr=given)["budget_inr"] == 350000


# ---------- invalid input: each names the field ----------

REQUIRED = ["departure_city", "country", "start_date", "nights", "adults", "budget_inr"]


@pytest.mark.parametrize("field", REQUIRED)
def test_missing_required_field(cat, field):
    rejected(cat, field, {k: v for k, v in VALID.items() if k != field})


@pytest.mark.parametrize("field", REQUIRED)
@pytest.mark.parametrize("blank", [None, "", "   "])
def test_blank_required_field(cat, field, blank):
    rejected(cat, field, dict(VALID, **{field: blank}))


INVALID = {
    "departure_city": [123, ["BLR"], "x" * 100],  # other text is accepted: see test_unknown_departure.py
    "country": ["France", "Tokyo", "UAE ", 1],
    "start_date": ["2027-02-30", "10/04/2027", "2027-4-10x", "tomorrow", 20270410],
    "nights": [0, 2, 11, -1, 6.5, "six", "6.5", True, [6]],
    "adults": [0, -1, 1.5, "two", False, [2]],
    "child_ages": [[18], [-1], [6.5], ["six"], [None], [True], 6, "6"],
    "budget_inr": [0, -1, "abc", "-5", True, float("nan"), float("inf")],
}
CASES = [(f, v) for f, vals in INVALID.items() for v in vals]


@pytest.mark.parametrize("field,value", CASES, ids=[f"{f}={v!r}" for f, v in CASES])
def test_invalid_value_rejected(cat, field, value):
    rejected(cat, field, dict(VALID, **{field: value}))


def test_not_an_object_rejected(cat):
    with pytest.raises(InvalidRequest):
        validate_request(["BLR", "Japan"], cat)


# ---------- the form's dropdowns come from destinations.json ----------

def test_options_endpoint_lists_departure_cities_and_countries(client):
    r = client.get("/api/options")
    assert r.status_code == 200
    body = r.json()
    assert {(c["airport"], c["city"]) for c in body["departure_cities"]} == {
        ("BLR", "Bengaluru"), ("DEL", "Delhi"), ("BOM", "Mumbai"), ("MAA", "Chennai")}
    assert set(body["countries"]) == {"Japan", "United Arab Emirates"}
