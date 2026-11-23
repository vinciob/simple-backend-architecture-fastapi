"""Shared JSON conventions match the TypeScript showcase contracts."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Identifier = Annotated[str, Field(pattern=r"^[a-fA-F0-9]{24}$")]


class APIModel(BaseModel):
    """Base class for all API models.

    Provides common configuration for JSON serialization, including camelCase aliasing
    and strict validation rules.
    """
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", str_strip_whitespace=False
    )
