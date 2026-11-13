"""POST /api/packages/results: adding children drops attractions that are not child friendly."""
import pytest

from tests.check_trip import load_catalog

J = load_catalog()
BASE = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
        "adults": 2, "child_ages": [], "budget_inr": 1_000_000}


def attractions(client, **changes):
    r = client.post("/api/packages/results", json=dict(BASE, **changes))
    assert r.status_code == 201, r.text
    return {i["catalog_id"] for p in r.json()["packages"] for i in p["items"] if i["type"] == "attraction"}


def friendly(ids, flag):
    return {a for a in ids if J["attractions"][a]["child_friendly"] is flag}


def test_without_children_unfriendly_attractions_are_offered(client):
    # guards the next test: if nothing unfriendly ever shows up, "children remove them" proves nothing
    assert friendly(attractions(client), False)


@pytest.mark.parametrize("ages", [[6], [0], [17], [3, 12]])
def test_with_children_no_unfriendly_attraction_is_offered(client, ages):
    assert not friendly(attractions(client, child_ages=ages), False)


def test_adding_a_child_removes_exactly_the_unfriendly_ones(client):
    without, with_kid = attractions(client), attractions(client, child_ages=[6])
    assert friendly(without, False)
    assert with_kid and not friendly(with_kid, False)
