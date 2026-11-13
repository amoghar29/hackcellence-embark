"""Response bodies of docs/API.md that have a fixed shape. The Package itself stays a dict (see services.package)."""
from datetime import date
from typing import Any

from pydantic import BaseModel

Package = dict[str, Any]


class DepartureCity(BaseModel):
    airport: str
    city: str


class FormRules(BaseModel):
    min_nights: int
    max_nights: int
    min_nights_per_city: int
    first_night: date
    last_departure: date


class FormOptions(BaseModel):
    departure_cities: list[DepartureCity]
    countries: list[str]
    rules: FormRules


class Credits(BaseModel):
    markdown: str


class Booking(BaseModel):
    reference: str
    package: Package


class HotelOption(BaseModel):
    hotel_id: str
    room_id: str
    name: str
    area: str
    stars: int
    rating: float
    room_type: str
    rooms: int
    price_inr: int
    price_diff_inr: int
    image: str
    preview: dict | None = None  # the package this option gives; see docs/API.md


class FlightOption(BaseModel):
    flight_id: str
    flight_number: str
    airline: str
    from_airport: str
    to_airport: str
    departure: str
    arrival: str
    stops: int
    duration_minutes: int
    price_inr: int
    price_diff_inr: int
    preview: dict | None = None  # the package this option gives; see docs/API.md


class AttractionOption(BaseModel):
    attraction_id: str
    name: str
    category: str
    start: str
    end: str
    price_inr: int
    image: str
    preview: dict | None = None  # the package this option gives; see docs/API.md


class PlanStop(BaseModel):
    city: str
    nights: int


class CityPlanOption(BaseModel):
    plan: list[PlanStop]
    total_inr: int
    price_diff_inr: int
    fits_budget: bool
    is_current: bool
    preview: dict | None = None  # the package this option gives; see docs/API.md


class CityPlanOptions(BaseModel):
    options: list[CityPlanOption]


class HotelOptions(BaseModel):
    options: list[HotelOption]


class FlightOptions(BaseModel):
    options: list[FlightOption]


class AttractionOptions(BaseModel):
    options: list[AttractionOption]
    reason: str | None = None  # why there are no options on that day
