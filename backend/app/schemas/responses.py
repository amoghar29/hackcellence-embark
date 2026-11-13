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


class AttractionOption(BaseModel):
    attraction_id: str
    name: str
    category: str
    start: str
    end: str
    price_inr: int
    image: str


class HotelOptions(BaseModel):
    trip_id: str
    options: list[HotelOption]


class FlightOptions(BaseModel):
    trip_id: str
    options: list[FlightOption]


class AttractionOptions(BaseModel):
    trip_id: str
    options: list[AttractionOption]
