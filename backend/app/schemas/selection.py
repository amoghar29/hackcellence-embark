"""The choices behind a package (which flight, room, transfer, visit, and when), as the client sends them back.

Dates and times travel as ISO text; model_validate turns them into date and datetime, which is what the builder,
changes and package modules use. dump() is the other way: JSON-safe text for the Package's `selection` field.
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AirportLeg(BaseModel):
    flight_id: str
    transfer_id: str
    pickup: datetime


class CityLeg(BaseModel):
    transfer_id: str
    pickup: datetime


class Stay(BaseModel):
    hotel_id: str
    room_id: str
    rooms: int = Field(ge=1)
    check_in: date
    check_out: date


class Visit(BaseModel):
    attraction_id: str
    start: datetime


class Selection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    arrival: AirportLeg
    return_: AirportLeg = Field(alias="return")
    stays: list[Stay] = Field(min_length=1)
    intercity: list[CityLeg]
    attractions: list[Visit]


def parse(raw) -> dict:
    """The selection dict (dates and datetimes as objects). Raises pydantic.ValidationError."""
    return Selection.model_validate(raw).model_dump(by_alias=True)


def dump(selection: dict) -> dict:
    return Selection.model_validate(selection).model_dump(by_alias=True, mode="json")
