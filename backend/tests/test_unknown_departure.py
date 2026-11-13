"""The traveler may type any departure city. One with no flights in the catalog gets a clear "no flights" answer,
not a form error, plus the cities that do have flights."""
import pytest

MENON = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}


@pytest.mark.parametrize("city", ["Paris", "xyz", "  New   York ", "NRT"])
@pytest.mark.parametrize("path", ["/api/packages/search", "/api/packages/results"])
def test_city_without_flights_is_a_clear_no_package(client, path, city):
    r = client.post(path, json=dict(MENON, departure_city=city))
    body = r.json()
    assert r.status_code == 422 and body["code"] == "NO_PACKAGE", r.text
    assert body["error"] == f"No flights exist from {' '.join(city.split())}.", body["error"]
    assert body["blockers"][0]["code"] == "NO_DEPARTURE_FLIGHTS" and body["blockers"][0]["part"] == "flight"
    assert body["suggestion"].strip()


def test_suggests_departure_cities_that_work(client):
    body = client.post("/api/packages/search", json=dict(MENON, departure_city="Paris")).json()
    assert body["alternatives"], body
    for a in body["alternatives"]:
        assert set(a["change"]) == {"departure_city"} and a["total_inr"] <= MENON["budget_inr"]
        # the suggestion really works
        assert client.post("/api/packages/search", json=dict(MENON, **a["change"])).status_code == 201


@pytest.mark.parametrize("value", [123, ["BLR"], {"a": 1}, "x" * 100])
def test_departure_that_is_not_a_city_name_is_still_a_form_error(client, value):
    r = client.post("/api/packages/search", json=dict(MENON, departure_city=value))
    assert r.status_code == 400 and r.json()["code"] == "INVALID_REQUEST" and r.json()["field"] == "departure_city"


@pytest.mark.parametrize("given", ["BLR", "blr", " Bengaluru ", "bengaluru"])
def test_known_cities_still_work_by_code_or_name(client, given):
    r = client.post("/api/packages/search", json=dict(MENON, departure_city=given))
    assert r.status_code == 201 and r.json()["traveler"]["home_airport"] == "BLR"
