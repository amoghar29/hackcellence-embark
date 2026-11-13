"""The app's rule validator (app.services.validator) against every travel rule in section 4.

validate(trip, cat) -> list of "CODE: message" strings; empty list = the package is correct.
Rule-breaking edits of the valid Menon fixture are in tests/mutations.py.
"""
import pytest

from app.services.validator import validate
from tests.mutations import MUTATIONS, item, retotal


def codes(trip, cat):
    return {v.split(":")[0] for v in validate(trip, cat)}


def test_valid_menon_package(menon_trip, cat):
    assert validate(menon_trip, cat) == []


def test_booked_package_is_still_valid(menon_trip, cat):
    for it in menon_trip["items"]:
        it["status"] = "BOOKED"
        it["booking"] = {"reference": "1234567890"}
    assert validate(menon_trip, cat) == []


def test_price_within_one_percent_is_accepted(menon_trip, cat):
    item(menon_trip, "i3")["price_inr"] += 100  # 28392 -> 28492, 0.35%
    retotal(menon_trip)
    assert validate(menon_trip, cat) == []


@pytest.mark.parametrize("name", MUTATIONS)
def test_broken_rule_is_reported(menon_trip, cat, name):
    code, mutate = MUTATIONS[name]
    mutate(menon_trip)
    assert code in codes(menon_trip, cat)


def test_edited_package_may_have_an_empty_full_day(menon_trip, cat):
    # "1-2 attractions on every full day" applies to the first package only
    code, mutate = MUTATIONS["full_day_without_attraction"]
    mutate(menon_trip)
    assert code in codes(menon_trip, cat)
    assert validate(menon_trip, cat, first_package=False) == []


@pytest.mark.parametrize("field", ["item_id", "type", "catalog_id", "price_inr", "start"])
def test_item_missing_a_required_field(menon_trip, cat, field):
    del item(menon_trip, "i5")[field]
    assert "FORMAT" in codes(menon_trip, cat)
