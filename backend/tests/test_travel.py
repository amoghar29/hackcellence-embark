"""Travel time between two places (app.services.travel). Always Google's: no formula estimate.

  travel.fetch(origins, destinations, key) -> [(from_id, to_id, minutes, meters, "google")], [] on any failure
  travel.Travel(cache, key, save).leg(a, b) -> the cached Google leg, else fetched from Google now (and saved);
      raises travel.TravelUnavailable when Google gives no time (no key, network down, no route)
  travel.for_catalog(cat) -> a Travel over the travel_times table (read once per catalog repository)
The warm-up command (python -m app.services.travel --warm) prefills the cache so search rarely waits on Google.
"""
import json

import pytest

from app.services import builder, travel
from app.services.request_form import validate_request
from tests.conftest import MENON_REQUEST, FakeResponse

TOKYO_STATION = {"hotel_id": "H", "lat": 35.6812, "lng": 139.7671}
SENSOJI = {"attraction_id": "A", "lat": 35.7148, "lng": 139.7967}


def test_there_is_no_formula_estimate():
    assert not hasattr(travel, "estimate")


def test_place_id_comes_from_any_catalog_record():
    assert travel.place_id(TOKYO_STATION) == "H" and travel.place_id(SENSOJI) == "A"
    assert travel.place_id({"code": "NRT", "lat": 0, "lng": 0}) == "NRT"


def test_fetch_reads_the_routes_api_route_matrix(monkeypatch):
    # Routes API computeRouteMatrix (the legacy Distance Matrix API cannot be enabled on new projects).
    # proto3 JSON leaves out zero values, so index 0 may be missing.
    body = [{"destinationIndex": 0, "duration": "1260s", "distanceMeters": 6200, "condition": "ROUTE_EXISTS", "status": {}},
            {"originIndex": 0, "destinationIndex": 1, "condition": "ROUTE_NOT_FOUND", "status": {}}]
    seen = []

    def fake(req, timeout):
        seen.append(req)
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr(travel, "urlopen", fake)
    other = {"attraction_id": "B", "lat": 35.0, "lng": 139.0}
    rows = travel.fetch([TOKYO_STATION], [SENSOJI, other], "k3y")
    assert rows == [("H", "A", 21, 6200, "google")]  # 1260 s rounds up to 21 min; a missing route is skipped
    (req,) = seen
    assert req.full_url == travel.MATRIX_URL and req.get_header("X-goog-api-key") == "k3y"
    sent = json.loads(req.data)
    assert sent["origins"][0]["waypoint"]["location"]["latLng"] == {"latitude": 35.6812, "longitude": 139.7671}
    assert len(sent["destinations"]) == 2 and sent["travelMode"] == "DRIVE"


def test_failed_fetch_returns_nothing(monkeypatch):
    def boom(req, timeout):
        raise OSError("network down")  # urllib's HTTPError (403 when the API is not enabled) is an OSError too

    monkeypatch.setattr(travel, "urlopen", boom)
    assert travel.fetch([TOKYO_STATION], [SENSOJI], "k3y") == []
    monkeypatch.setattr(travel, "urlopen", lambda req, timeout: FakeResponse(b'{"error": {"code": 403}}'))
    assert travel.fetch([TOKYO_STATION], [SENSOJI], "k3y") == []


def test_cached_leg_is_used_without_calling_google(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("a cached pair must not call Google")

    monkeypatch.setattr(travel, "urlopen", no_network)
    t = travel.Travel({("H", "A"): (7, 1000, "google")}, key="k3y", save=lambda rows: None)
    assert t.leg(TOKYO_STATION, SENSOJI) == {"minutes": 7, "km": 1.0, "source": "google"}
    assert t.minutes(TOKYO_STATION, SENSOJI) == 7


def test_missing_leg_is_fetched_from_google_once_and_saved(monkeypatch):
    calls, saved = [], []
    body = [{"duration": "600s", "distanceMeters": 3000, "condition": "ROUTE_EXISTS"}]

    def fake(req, timeout):
        calls.append(req)
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr(travel, "urlopen", fake)
    t = travel.Travel({}, key="k3y", save=saved.extend)
    assert t.leg(SENSOJI, TOKYO_STATION) == {"minutes": 10, "km": 3.0, "source": "google"}
    assert t.leg(SENSOJI, TOKYO_STATION)["minutes"] == 10
    assert len(calls) == 1 and saved == [("A", "H", 10, 3000, "google")]


def test_no_google_time_raises_instead_of_guessing(monkeypatch):
    with pytest.raises(travel.TravelUnavailable):
        travel.Travel({}, key="", save=lambda rows: None).leg(TOKYO_STATION, SENSOJI)  # no key
    monkeypatch.setattr(travel, "urlopen", lambda req, timeout: FakeResponse(b"[]"))  # no route
    with pytest.raises(travel.TravelUnavailable):
        travel.Travel({}, key="k3y", save=lambda rows: None).leg(TOKYO_STATION, SENSOJI)


def test_search_gets_every_leg_from_google(cat):
    trip = builder.build(validate_request(MENON_REQUEST, cat), cat)
    legs = [i["details"][k] for i in trip["items"] if i["type"] == "attraction"
            for k in ("travel_from", "travel_back") if k in i["details"]]
    assert legs and all(leg["source"] == "google" for leg in legs)


def test_search_says_so_when_google_is_unreachable(client, monkeypatch):
    def boom(req, timeout):
        raise OSError("network down")

    monkeypatch.setattr(travel, "urlopen", boom)
    r = client.post("/api/packages/search", json=MENON_REQUEST)
    assert r.status_code == 503 and r.json()["code"] == "TRAVEL_UNAVAILABLE"


def test_for_catalog_reads_the_cache_table(cat):
    cat.conn.execute("INSERT INTO travel_times (from_id, to_id, minutes, meters, source) "
                     "VALUES ('H', 'A', 9, 2500, 'google')")
    assert travel.for_catalog(cat).leg(TOKYO_STATION, SENSOJI) == {"minutes": 9, "km": 2.5, "source": "google"}
    assert travel.for_catalog(cat) is travel.for_catalog(cat)  # read once per repository
