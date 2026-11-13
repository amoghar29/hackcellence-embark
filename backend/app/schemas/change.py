from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ChangeHotel(BaseModel):
    action: Literal["change_hotel"]
    city: str
    hotel_id: str
    room_id: str


class ChangeFlight(BaseModel):
    action: Literal["change_flight"]
    item_id: str
    flight_id: str


class AddAttraction(BaseModel):
    action: Literal["add_attraction"]
    attraction_id: str
    start: str = Field(description="Local start time, YYYY-MM-DDTHH:MM")


class RemoveAttraction(BaseModel):
    action: Literal["remove_attraction"]
    item_id: str


Change = Annotated[ChangeHotel | ChangeFlight | AddAttraction | RemoveAttraction, Field(discriminator="action")]
