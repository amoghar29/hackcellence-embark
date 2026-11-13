"""Blocker messages name the real reason (attractions, failed rule check). Helpers come from test_builder."""
from app.services import builder, validator
from tests.test_builder import HUGE, codes, doctor, no_package


def message(exc, code):
    return next(b["message"] for b in exc.blockers if b["code"] == code)


def test_attraction_blocker_says_nothing_is_child_friendly(cat):
    c = doctor(cat, "attractions", "attraction_id", lambda a: dict(a, child_friendly=False))
    exc = no_package(c)  # the Menon family travels with a 6-year-old
    assert "NOT_ENOUGH_ATTRACTIONS" in codes(exc)
    assert "child-friendly" in message(exc, "NOT_ENOUGH_ATTRACTIONS")


def test_attraction_blocker_says_all_are_closed(cat):
    c = doctor(cat, "attractions", "attraction_id", lambda a: dict(a, open_days=[]))
    exc = no_package(c, child_ages=[])
    assert "closed" in message(exc, "NOT_ENOUGH_ATTRACTIONS")


def test_attraction_blocker_says_the_rest_are_already_used(cat):
    one_per_city = {}
    for a in cat.list_attractions():
        one_per_city.setdefault(a["city"], a)
    keep = {a["attraction_id"] for a in one_per_city.values()}
    c = doctor(cat, "attractions", "attraction_id", lambda a: a if a["attraction_id"] in keep else None)
    exc = no_package(c, nights=10, child_ages=[], budget_inr=HUGE)
    assert "already" in message(exc, "NOT_ENOUGH_ATTRACTIONS")


def test_failed_rule_check_names_the_rule(cat, monkeypatch):
    monkeypatch.setattr(validator, "validate", lambda trip, cat, **kw: ["ATTRACTION_OPEN: Zoo is closed on 2027-04-11"])
    exc = no_package(cat, budget_inr=HUGE)
    blocker = next(b for b in exc.blockers if b["code"] == "RULE_CHECK")
    assert "ATTRACTION_OPEN" in blocker["message"] and "Zoo is closed" in blocker["message"]
    assert blocker["part"] == "attraction"
