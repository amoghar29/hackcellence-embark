"""The catalog repository: every method runs its own SELECT on the catalog tables."""
from datetime import date

from app.repositories.catalog_repo import CatalogRepository


def test_get_by_id(cat):
    assert cat.get_flight("FL-711")["flight_id"] == "FL-711"
    assert cat.get_room("RM-TYO-001-A")["room_id"] == "RM-TYO-001-A"
    assert cat.get_transfer("TR-TYO-KYO-01")["transfer_id"] == "TR-TYO-KYO-01"
    assert cat.get_attraction("ATT-KYO-001")["attraction_id"] == "ATT-KYO-001"
    hotel = cat.get_hotel(cat.get_room("RM-TYO-001-A")["hotel_id"])
    assert hotel["city"] == "Tokyo" and isinstance(hotel["rating"], float)
    assert cat.get_airport("BLR")["code"] == "BLR"


def test_get_unknown_id_is_none(cat):
    for get in (cat.get_flight, cat.get_hotel, cat.get_room, cat.get_transfer, cat.get_attraction, cat.get_airport):
        assert get("NOPE") is None
    assert cat.get_flight(None) is None


def test_arriving_flights_land_that_day_at_an_airport_serving_the_city(cat):
    day = date(2027, 4, 10)
    found = cat.flights("BLR", ["Tokyo"], day, arriving=True)
    assert found
    assert all(f["from_airport"] == "BLR" and f["arrival_local"].date() == day and cat.serves(f["to_airport"], "Tokyo")
               for f in found)


def test_returning_flights_leave_that_day_from_an_airport_serving_a_city(cat):
    day = date(2027, 4, 16)
    cities = [c["name"] for c in cat.country("Japan")["cities"]]
    found = cat.flights("BLR", cities, day, arriving=False)
    assert found
    assert all(f["to_airport"] == "BLR" and f["departure_local"].date() == day
               and any(cat.serves(f["from_airport"], c) for c in cities) for f in found)
    assert cat.flights("BLR", ["Nowhere"], day, arriving=False) == []


def test_rooms_in_city(cat):
    rooms = cat.rooms_in("Tokyo")
    assert "RM-TYO-001-A" in {r["room_id"] for r in rooms}
    assert all(cat.get_hotel(r["hotel_id"])["city"] == "Tokyo" for r in rooms)


def test_rooms_of_hotel(cat):
    hotel_id = cat.get_room("RM-TYO-001-A")["hotel_id"]
    rooms = cat.rooms_of(hotel_id)
    assert "RM-TYO-001-A" in {r["room_id"] for r in rooms}
    assert all(r["hotel_id"] == hotel_id for r in rooms)
    assert cat.rooms_of("NOPE") == []


def test_rooms_left(cat):
    row = cat.conn.execute("SELECT * FROM availability WHERE rooms_left > 0 LIMIT 1").fetchone()
    assert cat.rooms_left(row["room_id"], row["date"]) == row["rooms_left"]
    assert cat.rooms_left(row["room_id"], date(1999, 1, 1)) == 0
    assert cat.rooms_left("NOPE", row["date"]) == 0


def test_airport_transfers_for_the_hotel_area(cat):
    t = cat.get_transfer("TR-NRT-ASA-TAXI")
    found = cat.airport_transfers(t["airport"], t["city"], t["area"])
    assert t in found
    assert all(x["airport"] == t["airport"] and x["city"] == t["city"] and x["area"] in (None, t["area"]) for x in found)


def test_attractions_in_city(cat):
    found = cat.attractions_in("Kyoto")
    assert "ATT-KYO-001" in {a["attraction_id"] for a in found}
    assert all(a["city"] == "Kyoto" for a in found)
    assert len(cat.list_attractions()) > len(found)


def test_a_new_repository_sees_changed_rows(cat):
    cat.get_flight("FL-711")
    cat.conn.execute("UPDATE flights SET seats_left = 0 WHERE flight_id = 'FL-711'")
    assert CatalogRepository(cat.conn).get_flight("FL-711")["seats_left"] == 0
