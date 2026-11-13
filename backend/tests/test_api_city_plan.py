"""G3: the traveler can choose another city plan; the package is built again (G2: with the price difference).

Nothing is saved: the calls send the package's request and selection and get the new package back.
"""
import pytest

from tests.check_trip import check, load_catalog
from tests.test_api import package_body

CAT = load_catalog()
MENON = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}


@pytest.fixture
def pkg(client):
    r = client.post("/api/packages/search", json=MENON)
    assert r.status_code == 201, r.text
    return r.json()


def plan_of(trip):
    return [{"city": c["city"], "nights": c["nights"]} for c in trip["cities"]]


def options(client, trip):
    r = client.post("/api/packages/options/city-plans", json=package_body(trip))
    assert r.status_code == 200, r.text
    return r.json()["options"]


def change_plan(client, trip, plan):
    return client.post("/api/packages/change", json=dict(package_body(trip), change={
        "action": "change_city_plan", "plan": plan}))


def test_options_show_price_difference_and_budget(client, pkg):
    opts = options(client, pkg)
    assert opts
    current = [o for o in opts if o["is_current"]]
    assert len(current) == 1 and current[0]["plan"] == plan_of(pkg) and current[0]["price_diff_inr"] == 0
    for o in opts:
        assert sum(c["nights"] for c in o["plan"]) == pkg["nights"]
        assert o["price_diff_inr"] == o["total_inr"] - pkg["total_inr"]
        assert o["fits_budget"] == (o["total_inr"] <= pkg["budget_inr"])
    assert [o["total_inr"] for o in opts] == sorted(o["total_inr"] for o in opts)


def test_change_city_plan_builds_the_package_again(client, pkg):
    other = next(o for o in options(client, pkg) if not o["is_current"])
    r = change_plan(client, pkg, other["plan"])
    assert r.status_code == 200, r.text
    new = r.json()
    assert plan_of(new) == other["plan"]
    assert new["total_inr"] == other["total_inr"]
    assert new["selection"] != pkg["selection"]
    assert check({k: v for k, v in new.items() if k != "notices"}, CAT, first_package=False) == []
    assert any(n["level"] == "INFO" for n in new["notices"])


def test_impossible_plan_is_refused_with_a_reason(client, pkg):
    bad = [{"city": "Tokyo", "nights": 1}, {"city": "Kyoto", "nights": pkg["nights"] - 1}]  # 1 night is too few
    r = change_plan(client, pkg, bad)
    body = r.json()
    assert r.status_code == 422 and body["code"] == "CHANGE_REFUSED" and body["reasons"]


def test_plan_with_wrong_total_nights_is_refused(client, pkg):
    r = change_plan(client, pkg, [{"city": "Tokyo", "nights": pkg["nights"] + 2}])
    assert r.status_code == 422 and r.json()["code"] == "CHANGE_REFUSED"


def test_plan_with_cities_that_are_not_linked_is_refused(client, pkg):
    r = change_plan(client, pkg, [{"city": "Tokyo", "nights": 3}, {"city": "Atlantis", "nights": pkg["nights"] - 3}])
    assert r.status_code == 422 and r.json()["code"] == "CHANGE_REFUSED"
