"""Request form (M1): the search body as the normalized request dict. The rules live in schemas.search."""
from pydantic import ValidationError

from app.schemas.search import SearchRequest


class InvalidRequest(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


def validate_request(raw, cat) -> dict:
    """Raises InvalidRequest naming the first bad field, with a message that says how to fix it."""
    try:
        return SearchRequest.model_validate(raw, context={"cat": cat}).model_dump()
    except ValidationError as e:
        err = e.errors()[0]
        field = err["loc"][0] if err["loc"] else None
        raise InvalidRequest(field, f"{field} is required." if err["type"] == "missing" else err["msg"]) from None
