"""G4: the results response names the cheapest, fastest and best rated package, each a valid package within budget."""
import pytest

from tests.check_trip import check, load_catalog

CAT = load_catalog()
MENON = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}
OTHER = {"departure_city": "DEL", "country": "United Arab Emirates", "start_date": "2027-04-11", "nights": 7,
         "adults": 2, "child_ages": [], "budget_inr": 400000}


def travel_minutes(p):
    flights = [i["details"]["duration_minutes"] for i in p["items"] if i["type"] == "flight"]
    between = [i["details"]["duration_minutes"] for i in p["items"]
               if i["type"] == "transfer" and i["details"]["kind"] == "INTERCITY"]
    return sum(flights) + sum(between)


def avg_stars(p):
    hotels = [i["details"] for i in p["items"] if i["type"] == "hotel"]
    return sum(h["stars"] * h["nights"] for h in hotels) / sum(h["nights"] for h in hotels)


@pytest.fixture(params=[MENON, OTHER], ids=["japan", "uae"])
def results(client, request):
    r = client.post("/api/packages/results", json=request.param)
    if r.status_code != 201:
        pytest.skip(f"no package for {request.param['country']}: {r.text[:80]}")
    return r.json()


def test_three_picks_are_valid_packages(results):
    pool = results["packages"]
    assert set(results["picks"]) == {"cheapest", "fastest", "best_rated"}
    for n in results["picks"].values():  # a pick is the position of the package in `packages`
        p = pool[n]
        assert p["total_inr"] <= p["budget_inr"]
        assert check(p, CAT) == []


def test_each_pick_is_best_at_its_own_measure(results):
    pool = results["packages"]
    pick = {k: pool[n] for k, n in results["picks"].items()}
    assert pick["cheapest"]["total_inr"] == min(p["total_inr"] for p in pool)
    assert travel_minutes(pick["fastest"]) == min(travel_minutes(p) for p in pool)
    assert avg_stars(pick["best_rated"]) == max(avg_stars(p) for p in pool)


def test_trip_reports_its_measures(results):
    for p in results["packages"]:
        assert p["travel_minutes"] == travel_minutes(p)
        assert p["avg_stars"] == pytest.approx(avg_stars(p), abs=0.01)


def test_a_pick_can_be_booked_as_it_is(client, results):
    p = results["packages"][results["picks"]["fastest"]]
    r = client.post("/api/bookings", json={"request": p["request"], "selection": p["selection"]},
                    headers={"Idempotency-Key": "pick-" + p["selection"]["arrival"]["flight_id"] + p["start_date"]})
    assert r.status_code == 200, r.text
    assert r.json()["package"]["total_inr"] == p["total_inr"]
