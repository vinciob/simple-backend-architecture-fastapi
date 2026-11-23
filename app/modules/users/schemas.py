"""Schemas for user-related operations."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BeforeValidator, EmailStr, Field

from app.core.schemas import APIModel


def normalize_email(value: Any) -> Any:
    """Normalize the email by stripping whitespace and converting to lowercase."""
    return value.strip().lower() if isinstance(value, str) else value


Email = Annotated[EmailStr, BeforeValidator(normalize_email), Field(max_length=254)]
Name = Annotated[
    str,
    BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
    Field(min_length=2, max_length=100),
]


class RegisterInput(APIModel):
    """Schema for user registration input."""
    name: Name
    email: Email
    password: str = Field(min_length=12, max_length=128)


class UserResponse(APIModel):
    """Schema for user response."""
    id: str
    name: str
    email: str
    created_at: datetime

class RegisterResponse(APIModel):
    """Schema for user registration response."""
    user: UserResponse
