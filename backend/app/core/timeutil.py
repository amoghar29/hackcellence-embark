"""Clock times. Every time in the catalog is local to its place and has no offset:
compare times at one place only, and never subtract times of two different places."""
from datetime import datetime, timedelta

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def parse_hhmm(s):
    """'06:30' -> 390. '24:00' -> 1440 (midnight at the end of the day)."""
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def in_window(minute, frm, until):
    """Both ends included. until < from means the window runs past midnight."""
    f, u = parse_hhmm(frm), parse_hhmm(until)
    if f <= u:
        return f <= minute <= u or (u == 1440 and minute == 0)
    return minute >= f or minute <= u


def minute_of_day(dt):
    return dt.hour * 60 + dt.minute


def fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def in_service(transfer, dt):
    """The pickup time is inside the service hours and, for trains and buses, on a departure."""
    m = minute_of_day(dt)
    if not in_window(m, transfer["service_from"], transfer["service_until"]):
        return False
    freq = transfer.get("frequency_minutes")
    return not freq or (m - parse_hhmm(transfer["service_from"])) % 1440 % freq == 0


def first_pickup(transfer, earliest, wait_minutes):
    """First in-service pickup at or after `earliest`, waiting at most `wait_minutes`. None if there is none."""
    for m in range(wait_minutes + 1):
        dt = earliest + timedelta(minutes=m)
        if in_service(transfer, dt):
            return dt
    return None


def last_pickup(transfer, latest):
    """Latest in-service pickup at or before `latest`, on the same calendar day. None if there is none."""
    dt = latest
    while dt.date() == latest.date():
        if in_service(transfer, dt):
            return dt
        dt -= timedelta(minutes=1)
    return None


def at(day, hhmm):
    return datetime.combine(day, datetime.min.time()) + timedelta(minutes=parse_hhmm(hhmm))
