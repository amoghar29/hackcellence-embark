"""check_trip.py is the independent judge in the API tests, so it must catch every broken rule too."""
import pytest

from tests.check_trip import check
from tests.mutations import J, MUTATIONS, item, retotal


def test_accepts_valid_menon_package(menon_trip):
    assert check(menon_trip, J) == []


def test_accepts_price_within_one_percent(menon_trip):
    item(menon_trip, "i3")["price_inr"] += 100
    retotal(menon_trip)
    assert check(menon_trip, J) == []


@pytest.mark.parametrize("name", MUTATIONS)
def test_catches_broken_rule(menon_trip, name):
    _, mutate = MUTATIONS[name]
    mutate(menon_trip)
    assert check(menon_trip, J) != []
