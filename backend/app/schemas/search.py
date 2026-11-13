"""Search request (M1): the 7 form fields plus the optional cities and theme, checked and normalized.
Messages say how to fix the value.

The catalog rules (departure cities, countries, nights, data window) come in through the validation context:
SearchRequest.model_validate(raw, context={"cat": cat}). Pydantic's own coercion is too loose here (True -> 1)
and too strict there ("3,50,000", " 2027-04-10 "), so every field parses its input itself.
"""
import math
import re
from datetime import date, timedelta
from typing import Annotated, Any

from pydantic import (BaseModel, BeforeValidator, Field, ValidationError, ValidationInfo, computed_field,
                      field_validator, model_validator)
from pydantic_core import PydanticCustomError

# a theme prefers attractions of these categories; "mixed" (the default) has no preference
THEMES = {"mixed": set(),
          "spiritual": {"TEMPLE", "SHRINE", "MOSQUE"},
          "adventure": {"THEME_PARK", "NATURE", "BEACH", "PARK", "VIEWPOINT"},
          "culture": {"MUSEUM", "CASTLE", "PALACE", "MONUMENT", "DISTRICT", "MARKET"}}
REQUIRED = ("departure_city", "country", "start_date", "nights", "adults", "budget_inr")


def _invalid(message: str) -> PydanticCustomError:
    return PydanticCustomError("invalid_request", message)


def _whole(value: Any, label: str) -> int:
    """int from an int, a whole float or a digit string. bool, 6.5, 'six' and lists are refused."""
    if isinstance(value, str) and len(value) < 30 and re.fullmatch(r"\s*-?\d+\s*", value):
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) < 10**12:
        return value
    if isinstance(value, float) and math.isfinite(value) and abs(value) < 10**12 and value == int(value):
        return int(value)
    raise _invalid(f"{label} must be a whole number.")


def _destinations(info: ValidationInfo) -> dict:
    return info.context["cat"].destinations


ChildAge = Annotated[int, BeforeValidator(lambda v: _whole(v, "Each child's age"))]


class SearchRequest(BaseModel):
    departure_city: str = Field(description="Airport code or city name, e.g. BLR or Bengaluru")
    country: str = Field(description="A country from GET /api/options")
    start_date: date = Field(description="First night, YYYY-MM-DD")
    nights: int
    adults: int
    child_ages: list[ChildAge] = Field(default=[], description="One age (0-17) per child")
    budget_inr: int = Field(description="Whole rupees; commas are allowed, e.g. 3,50,000")
    cities: list[str] = Field(default=[], description="Optional: cities every package must visit")
    theme: str = Field(default="mixed", description="Optional: " + ", ".join(THEMES))

    @computed_field
    @property
    def end_date(self) -> date:
        """The return-flight day."""
        return self.start_date + timedelta(self.nights)

    @model_validator(mode="before")
    @classmethod
    def _blank_is_missing(cls, raw: Any) -> dict:
        if not isinstance(raw, dict):
            raise _invalid("Send the request as a JSON object with the form fields.")
        return {k: v for k, v in raw.items()
                if not (k in REQUIRED and (v is None or isinstance(v, str) and not v.strip()))}

    @field_validator("departure_city", mode="before")
    @classmethod
    def _airport(cls, v: Any, info: ValidationInfo) -> str:
        """Any city is accepted. One we fly from becomes its airport code; any other is kept as typed, and the
        builder answers "no flights exist from ..." for it."""
        if not isinstance(v, str) or len(" ".join(v.split())) > 60:
            raise _invalid("Departure city must be a city name or an airport code.")
        text = " ".join(v.split())
        for d in _destinations(info)["departure_cities"]:
            if text.casefold() in (d["airport"].casefold(), d["city"].casefold()):
                return d["airport"]
        return text

    @field_validator("country", mode="before")
    @classmethod
    def _country(cls, v: Any, info: ValidationInfo) -> str:
        names = [c["name"] for c in _destinations(info)["countries"]]
        given = " ".join(v.split()).casefold() if isinstance(v, str) else None
        for name in names:
            if name.casefold() == given:
                return name
        raise _invalid("Country must be one of: " + ", ".join(names) + ".")

    @field_validator("start_date", mode="before")
    @classmethod
    def _date(cls, v: Any) -> date:
        text = v.strip() if isinstance(v, str) else ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            try:
                return date.fromisoformat(text)
            except ValueError:
                pass
        raise _invalid("Start date must be a real date written as YYYY-MM-DD.")

    @field_validator("nights", mode="before")
    @classmethod
    def _nights(cls, v: Any, info: ValidationInfo) -> int:
        rules = _destinations(info)["rules"]
        lo, hi = rules["min_nights"], rules["max_nights"]
        nights = _whole(v, "Nights")
        if not lo <= nights <= hi:
            raise _invalid(f"Nights must be between {lo} and {hi}.")
        return nights

    @field_validator("adults", mode="before")
    @classmethod
    def _adults(cls, v: Any) -> int:
        adults = _whole(v, "Adults")
        if adults < 1:
            raise _invalid("At least 1 adult must travel.")
        return adults

    @field_validator("child_ages", mode="before")
    @classmethod
    def _ages_list(cls, v: Any) -> list:
        if v is None:
            return []
        if not isinstance(v, list):
            raise _invalid("Children's ages must be a list with one age per child.")
        return v

    @field_validator("child_ages")
    @classmethod
    def _ages_range(cls, ages: list[int]) -> list[int]:
        if any(not 0 <= a <= 17 for a in ages):
            raise _invalid("A child's age must be between 0 and 17. Count anyone 18 or older as an adult.")
        return ages

    @field_validator("budget_inr", mode="before")
    @classmethod
    def _budget(cls, v: Any) -> int:
        budget = _whole(v.replace(",", "") if isinstance(v, str) else v, "Budget")
        if budget <= 0:
            raise _invalid("Budget must be more than 0.")
        if budget > 10**10:
            raise _invalid("Budget must be at most 10,00,00,00,000.")
        return budget

    @field_validator("cities", mode="before")
    @classmethod
    def _cities_list(cls, v: Any) -> list:
        if v is None:
            return []
        if not isinstance(v, list) or not all(isinstance(c, str) for c in v):
            raise _invalid("Cities must be a list of city names.")
        return v

    @field_validator("theme", mode="before")
    @classmethod
    def _theme(cls, v: Any) -> str:
        if v is None or isinstance(v, str) and not v.strip():
            return "mixed"
        if isinstance(v, str) and v.strip().casefold() in THEMES:
            return v.strip().casefold()
        raise _invalid("Theme must be one of: " + ", ".join(THEMES) + ".")

    @model_validator(mode="after")
    def _cities_of_country(self, info: ValidationInfo) -> "SearchRequest":
        """Picked cities become the country's spelling, once each, and must fit in the nights."""
        d = _destinations(info)
        names = next(c for c in d["countries"] if c["name"] == self.country)["cities"]
        by_key = {c["name"].casefold(): c["name"] for c in names}
        picked = []
        for text in self.cities:
            name = by_key.get(" ".join(text.split()).casefold())
            if name is None:
                message = f"{text.strip()} is not a city in {self.country}. Pick from: " + ", ".join(by_key.values()) + "."
                break
            if name not in picked:
                picked.append(name)
        else:
            least = len(picked) * d["rules"]["min_nights_per_city"]
            if least <= self.nights:
                self.cities = picked
                return self
            message = f"The {len(picked)} picked cities need at least {least} nights. Add nights or pick fewer cities."
        raise ValidationError.from_exception_data(type(self).__name__, [
            {"type": _invalid(message), "loc": ("cities",), "input": self.cities}])

    @model_validator(mode="after")
    def _in_data_window(self, info: ValidationInfo) -> "SearchRequest":
        window = _destinations(info)["rules"]["data_window"]
        first, last = date.fromisoformat(window["first_night"]), date.fromisoformat(window["last_departure"])
        if self.start_date < first:
            message = f"Trips start on or after {first}. Choose a later start date."
        elif self.end_date > last:
            message = (f"The trip must end by {last}. Start on or before {last - timedelta(self.nights)}, "
                       "or choose fewer nights.")
        else:
            return self
        # a check across two fields that still names start_date as the one to fix
        raise ValidationError.from_exception_data(type(self).__name__, [
            {"type": _invalid(message), "loc": ("start_date",), "input": self.start_date.isoformat()}])
