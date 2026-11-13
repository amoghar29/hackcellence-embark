"""A visit can run long: the builder keeps 15% of its visit time (rounded up to a minute) free after it, before the
STOP_BUFFER and the travel to the next visit or back to the hotel. The visit's own start and end stay as planned."""
import math
from datetime import datetime, timedelta

import pytest

from app.services import builder
from tests.test_builder import TRAVEL_CASES, day_plans, mins_of, req


def overrun(rec):
    return timedelta(minutes=math.ceil(rec["visit_minutes"] * 0.15))


@pytest.mark.parametrize("changes", TRAVEL_CASES.values(), ids=TRAVEL_CASES.keys())
def test_each_visit_leaves_15_percent_for_running_long(cat, changes):
    trip = builder.build(req(cat, **changes), cat)
    for day, (hotel, _, visits) in day_plans(trip).items():
        for (item, rec), (nxt, nrec) in zip(visits, visits[1:]):
            ready = datetime.fromisoformat(item["end"]) + overrun(rec) + timedelta(minutes=builder.STOP_BUFFER)
            assert datetime.fromisoformat(nxt["start"]) >= ready + mins_of(rec, nrec), f"{day}: {nrec['name']} too soon"
        item, rec = visits[-1]
        back = datetime.fromisoformat(item["end"]) + overrun(rec) + mins_of(rec, hotel)
        assert back <= datetime.fromisoformat(f"{day}T{builder.DAY_END}"), f"{day}: back at the hotel at {back}"


@pytest.mark.parametrize("changes", TRAVEL_CASES.values(), ids=TRAVEL_CASES.keys())
def test_built_package_has_no_travel_warnings(cat, changes):
    """The warnings (package.day_legs) use the same margin, so the builder's own days are never flagged."""
    trip = builder.build(req(cat, **changes), cat)
    flagged = [a["warnings"] for a in trip["items"] if a["type"] == "attraction" and a["warnings"]]
    assert flagged == []
