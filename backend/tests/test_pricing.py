from app.services import pricing


def test_flight_price_is_per_seat_for_every_traveler(cat):
    assert pricing.flight_price(cat.get_flight("FL-711"), 3) == 25200 * 3


def test_hotel_price_rooms_times_nights(cat):
    assert pricing.hotel_price(cat.get_room("RM-TYO-001-A"), 2, 3) == 6440 * 2 * 3


def test_per_person_transfer_uses_child_price(cat):
    t = cat.get_transfer("TR-TYO-KYO-01")
    assert pricing.transfer_price(t, 2, 1) == 2 * 7935 + 3968
    assert pricing.transfer_quantity(t, 2, 1) == 3


def test_per_person_transfer_without_child_price_uses_price(cat):
    t = dict(cat.get_transfer("TR-TYO-KYO-01"), child_price_inr=None)
    assert pricing.transfer_price(t, 2, 1) == 3 * 7935


def test_per_vehicle_transfer_rounds_vehicles_up(cat):
    t = cat.get_transfer("TR-NRT-ASA-TAXI")  # 4 seats, 13440 per vehicle
    assert pricing.transfer_quantity(t, 4, 0) == 1
    assert pricing.transfer_price(t, 4, 0) == 13440
    assert pricing.transfer_quantity(t, 3, 2) == 2
    assert pricing.transfer_price(t, 3, 2) == 2 * 13440
    assert pricing.transfer_quantity(t, 9, 0) == 3


def test_attraction_with_child_price(cat):
    assert pricing.attraction_price(cat.get_attraction("ATT-KYO-001"), 2, 1) == 2 * 280 + 112


def test_attraction_child_price_zero_is_a_price(cat):
    # child_price 0 means children are free, not "no child price"
    assert pricing.attraction_price(cat.get_attraction("ATT-TYO-005"), 2, 2) == 2 * 560


def test_attraction_without_child_price_uses_adult_price(cat):
    assert pricing.attraction_price(cat.get_attraction("ATT-DXB-004"), 2, 1) == 3 * 3412
