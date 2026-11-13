"""Bodies that carry a whole package back to the server: the request that built it and its selection."""
from typing import Any

from pydantic import BaseModel


class PackageBody(BaseModel):
    """Parsed in the service (the rules need the catalog); here only to document the shape in OpenAPI."""
    request: dict[str, Any]
    selection: dict[str, Any]
