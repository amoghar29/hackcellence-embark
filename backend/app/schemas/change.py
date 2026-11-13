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


class PlanStop(BaseModel):
    city: str
    nights: int


class ChangeCityPlan(BaseModel):
    action: Literal["change_city_plan"]
    plan: list[PlanStop] = Field(description="The cities in order, with the nights in each")


Change = Annotated[ChangeHotel | ChangeFlight | AddAttraction | RemoveAttraction | ChangeCityPlan,
                   Field(discriminator="action")]
