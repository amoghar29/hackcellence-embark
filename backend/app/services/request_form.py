"""Request form (M1): checks the 7 request fields and normalizes them. Messages say how to fix the value."""
import math
import re
from datetime import date, timedelta

REQUIRED = ["departure_city", "country", "start_date", "nights", "adults", "budget_inr"]


class InvalidRequest(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


def _whole(value, field, label):
    """int from an int, a whole float or a digit string. bool, 6.5, 'six' and lists are refused."""
    if isinstance(value, str) and re.fullmatch(r"\s*-?\d+\s*", value):
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and math.isfinite(value) and value == int(value):
        return int(value)
    raise InvalidRequest(field, f"{label} must be a whole number.")


def validate_request(raw, cat):
    if not isinstance(raw, dict):
        raise InvalidRequest(None, "Send the request as a JSON object with the 7 form fields.")
    for f in REQUIRED:
        v = raw.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            raise InvalidRequest(f, f"{f} is required.")
    rules = cat.destinations["rules"]

    departures = cat.destinations["departure_cities"]
    dep = raw["departure_city"].strip().casefold() if isinstance(raw["departure_city"], str) else None
    airport = next((d["airport"] for d in departures if dep in (d["airport"].casefold(), d["city"].casefold())), None)
    if not airport:
        raise InvalidRequest("departure_city", "Departure city must be one of: "
                             + ", ".join(f"{d['city']} ({d['airport']})" for d in departures) + ".")

    names = [c["name"] for c in cat.destinations["countries"]]
    given = " ".join(raw["country"].split()).casefold() if isinstance(raw["country"], str) else None
    country = next((n for n in names if n.casefold() == given), None)
    if not country:
        raise InvalidRequest("country", "Country must be one of: " + ", ".join(names) + ".")

    text = raw["start_date"].strip() if isinstance(raw["start_date"], str) else ""
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise ValueError
        start = date.fromisoformat(text)
    except ValueError:
        raise InvalidRequest("start_date", "Start date must be a real date written as YYYY-MM-DD.") from None

    lo, hi = rules["min_nights"], rules["max_nights"]
    nights = _whole(raw["nights"], "nights", "Nights")
    if not lo <= nights <= hi:
        raise InvalidRequest("nights", f"Nights must be between {lo} and {hi}.")

    adults = _whole(raw["adults"], "adults", "Adults")
    if adults < 1:
        raise InvalidRequest("adults", "At least 1 adult must travel.")

    ages = raw.get("child_ages")
    ages = [] if ages is None else ages
    if not isinstance(ages, list):
        raise InvalidRequest("child_ages", "Children's ages must be a list with one age per child.")
    ages = [_whole(a, "child_ages", "Each child's age") for a in ages]
    if any(not 0 <= a <= 17 for a in ages):
        raise InvalidRequest("child_ages", "A child's age must be between 0 and 17. Count anyone 18 or older as an adult.")

    b = raw["budget_inr"]
    budget = _whole(b.replace(",", "") if isinstance(b, str) else b, "budget_inr", "Budget")
    if budget <= 0:
        raise InvalidRequest("budget_inr", "Budget must be more than 0.")

    first = date.fromisoformat(rules["data_window"]["first_night"])
    last = date.fromisoformat(rules["data_window"]["last_departure"])
    end = start + timedelta(nights)
    if start < first:
        raise InvalidRequest("start_date", f"Trips start on or after {first}. Choose a later start date.")
    if end > last:
        raise InvalidRequest("start_date", f"The trip must end by {last}. Start on or before "
                                           f"{last - timedelta(nights)}, or choose fewer nights.")
    return {"departure_city": airport, "country": country, "start_date": start, "end_date": end, "nights": nights,
            "adults": adults, "child_ages": ages, "budget_inr": budget}
