"""Schemas for authentication-related API models."""
from typing import Literal

from pydantic import Field

from app.core.schemas import APIModel
from app.modules.users.schemas import Email


class LoginInput(APIModel):
    """Input schema for user login."""
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(APIModel):
    """Response schema for authentication tokens."""
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
