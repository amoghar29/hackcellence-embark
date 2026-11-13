from app.services.pricing import rooms_needed

TWIN = {"max_adults": 2, "max_children": 0}
FAMILY = {"max_adults": 2, "max_children": 2}
SINGLE = {"max_adults": 1, "max_children": 0}
TRIPLE = {"max_adults": 3, "max_children": 0}
FAMILY_SUITE = {"max_adults": 4, "max_children": 2}


def test_menon_family_needs_two_twins_or_one_family():
    assert rooms_needed(TWIN, 2, 1) == 2
    assert rooms_needed(FAMILY, 2, 1) == 1


def test_rooms_never_exceed_adults():
    # 1 adult + 2 children would need 2 twins, but each room needs an adult
    assert rooms_needed(TWIN, 1, 2) is None
    assert rooms_needed(SINGLE, 2, 1) is None


def test_larger_groups():
    assert rooms_needed(FAMILY_SUITE, 4, 3) == 2
    assert rooms_needed(TRIPLE, 9, 0) == 3
    assert rooms_needed(SINGLE, 1, 0) == 1
    assert rooms_needed(FAMILY, 1, 2) == 1
