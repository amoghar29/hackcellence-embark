from app.core.timeutil import in_window, parse_hhmm


def test_parse_hhmm():
    assert parse_hhmm("00:00") == 0
    assert parse_hhmm("06:30") == 390
    assert parse_hhmm("24:00") == 1440


def test_window_includes_both_ends():
    assert in_window(parse_hhmm("06:00"), "06:00", "23:00")
    assert in_window(parse_hhmm("23:00"), "06:00", "23:00")
    assert not in_window(parse_hhmm("05:59"), "06:00", "23:00")
    assert not in_window(parse_hhmm("23:01"), "06:00", "23:00")


def test_full_day_window():
    assert in_window(0, "00:00", "24:00")
    assert in_window(parse_hhmm("23:59"), "00:00", "24:00")
    assert in_window(parse_hhmm("23:59"), "05:00", "24:00")


def test_window_past_midnight():
    assert in_window(parse_hhmm("00:15"), "06:00", "00:30")
    assert in_window(parse_hhmm("00:30"), "06:00", "00:30")
    assert in_window(parse_hhmm("22:00"), "06:00", "00:30")
    assert not in_window(parse_hhmm("01:00"), "06:00", "00:30")
    assert not in_window(parse_hhmm("05:59"), "06:00", "00:30")
