"""Travel time between two places (app.services.travel).

  travel.estimate(a, b) -> {"minutes", "km", "source": "estimate"} from catalog lat/lng only
  travel.fetch(origins, destinations, key) -> [(from_id, to_id, minutes, meters, "google")], [] on any failure
  travel.Travel(cache).leg(a, b) -> the cached Google leg when there is one, else the estimate
  travel.for_catalog(cat) -> a Travel over the travel_times table (read once per catalog repository)
Search never calls Google: only the warm-up command (python -m app.services.travel --warm) does.
"""
import io
import json

import pytest

from app.services import builder, travel
from app.services.request_form import validate_request
from tests.conftest import MENON_REQUEST

TOKYO_STATION = {"hotel_id": "H", "lat": 35.6812, "lng": 139.7671}
SENSOJI = {"attraction_id": "A", "lat": 35.7148, "lng": 139.7967}


def test_same_place_takes_only_the_fixed_overhead():
    leg = travel.estimate(TOKYO_STATION, TOKYO_STATION)
    assert leg == {"minutes": travel.OVERHEAD_MINUTES, "km": 0.0, "source": "estimate"}


def test_estimate_across_central_tokyo_is_sane():
    leg = travel.estimate(TOKYO_STATION, SENSOJI)  # about 4.6 km in a straight line
    assert 20 <= leg["minutes"] <= 45 and leg["minutes"] % 5 == 0
    assert 5 <= leg["km"] <= 8
    assert travel.estimate(SENSOJI, TOKYO_STATION) == leg


def test_place_id_comes_from_any_catalog_record():
    assert travel.place_id(TOKYO_STATION) == "H" and travel.place_id(SENSOJI) == "A"
    assert travel.place_id({"code": "NRT", "lat": 0, "lng": 0}) == "NRT"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


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


def test_cached_leg_wins_over_the_estimate():
    t = travel.Travel({("H", "A"): (7, 1000, "google")})
    assert t.leg(TOKYO_STATION, SENSOJI) == {"minutes": 7, "km": 1.0, "source": "google"}
    assert t.leg(SENSOJI, TOKYO_STATION) == travel.estimate(SENSOJI, TOKYO_STATION)  # only that direction is cached
    assert t.minutes(TOKYO_STATION, SENSOJI) == 7


def test_search_never_calls_the_network(cat, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("search must not call Google")

    monkeypatch.setenv("GOOGLE_MAPS_KEY", "k3y")
    monkeypatch.setattr(travel, "urlopen", no_network)
    trip = builder.build(validate_request(MENON_REQUEST, cat), cat)
    assert trip["items"]


def test_for_catalog_reads_the_cache_table(cat):
    cat.conn.execute("INSERT INTO travel_times (from_id, to_id, minutes, meters, source) "
                     "VALUES ('H', 'A', 9, 2500, 'google')")
    assert travel.for_catalog(cat).leg(TOKYO_STATION, SENSOJI) == {"minutes": 9, "km": 2.5, "source": "google"}
    assert travel.for_catalog(cat) is travel.for_catalog(cat)  # read once per repository
