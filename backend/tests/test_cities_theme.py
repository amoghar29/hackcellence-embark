"""Optional search fields: `cities` (every picked city is in every package) and `theme` (a soft preference
for attractions of the theme's categories)."""
import pytest

from app.services.request_form import InvalidRequest, validate_request
from tests.check_trip import check, load_catalog

CAT = load_catalog()
BASE = {"departure_city": "BLR", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
        "adults": 2, "child_ages": [], "budget_inr": 1_000_000}
SPIRITUAL = {"TEMPLE", "SHRINE", "MOSQUE"}


def rejected(cat, field, **changes):
    with pytest.raises(InvalidRequest) as e:
        validate_request(dict(BASE, **changes), cat)
    assert e.value.field == field
    assert str(e.value).strip()


def packages(client, **changes):
    r = client.post("/api/packages/results", json=dict(BASE, **changes))
    assert r.status_code == 201, r.text
    found = r.json()["packages"]
    assert found
    for p in found:
        assert check(p, CAT) == []
    return found


# ---------- validation ----------

def test_cities_and_theme_default_to_none_picked_and_mixed(cat):
    got = validate_request(dict(BASE), cat)
    assert got["cities"] == [] and got["theme"] == "mixed"


def test_cities_are_normalized_and_deduplicated(cat):
    got = validate_request(dict(BASE, cities=[" kyoto ", "Kyoto", "OSAKA"], theme="Spiritual"), cat)
    assert got["cities"] == ["Kyoto", "Osaka"] and got["theme"] == "spiritual"


def test_null_and_blank_mean_not_picked(cat):
    got = validate_request(dict(BASE, cities=None, theme=""), cat)
    assert got["cities"] == [] and got["theme"] == "mixed"


def test_city_of_another_country_is_rejected(cat):
    rejected(cat, "cities", cities=["Dubai"])


def test_cities_must_be_a_list(cat):
    rejected(cat, "cities", cities="Kyoto")


def test_too_many_cities_for_the_nights_is_rejected(cat):
    rejected(cat, "cities", nights=4, cities=["Tokyo", "Kyoto", "Osaka"])


def test_unknown_theme_is_rejected(cat):
    rejected(cat, "theme", theme="party")


# ---------- cities ----------

@pytest.mark.parametrize("picked", [["Kyoto"], ["Osaka"], ["Tokyo", "Osaka"]])
def test_every_package_visits_every_picked_city(client, picked):
    for p in packages(client, cities=picked):
        assert set(picked) <= {c["city"] for c in p["cities"]}


def test_uae_city_pick(client):
    for p in packages(client, country="United Arab Emirates", cities=["Abu Dhabi"]):
        assert "Abu Dhabi" in {c["city"] for c in p["cities"]}


# ---------- theme ----------

def spiritual_visits(found):
    return sum(CAT["attractions"][i["catalog_id"]]["category"] in SPIRITUAL
               for p in found for i in p["items"] if i["type"] == "attraction")


def test_spiritual_theme_picks_more_temples_and_shrines(client):
    assert spiritual_visits(packages(client, theme="spiritual")) > spiritual_visits(packages(client))


def test_theme_never_fails_a_search(client):
    # the UAE has a single mosque: the theme is a preference, other attractions still fill the days
    packages(client, country="United Arab Emirates", theme="spiritual")


# ---------- form options ----------

def test_options_list_cities_per_country_and_themes(client):
    body = client.get("/api/options").json()
    assert set(body["cities"]["Japan"]) == {"Tokyo", "Kyoto", "Osaka"}
    assert set(body["cities"]["United Arab Emirates"]) == {"Dubai", "Abu Dhabi"}
    assert body["themes"] == ["mixed", "spiritual", "adventure", "culture"]
