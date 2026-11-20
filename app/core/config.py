"""Validated configuration; secrets are supplied by the environment, never source code."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Separate configuration for database and application settings.
# values are sourced from environment variables and validated by Pydantic.

class DatabaseSettings(BaseSettings):
    """Database settings for the application."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://showcase:showcase@localhost:5432/showcase"
    database_pool_size: int = Field(default=20, ge=1, le=200)

    @field_validator("database_url")
    @classmethod
    def require_async_postgres(cls, value: str) -> str:
        """Ensure the database URL uses the asyncpg driver."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        return value


class Settings(DatabaseSettings):
    """Application settings, including environment, JWT, and other configurations."""
    environment: Literal["development", "test", "production"] = "development"
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "fastapi-showcase"
    jwt_audience: str = "showcase-api"
    access_token_ttl: int = Field(default=600, ge=60, le=3600)
    refresh_token_ttl: int = Field(default=604800, ge=600, le=2592000)
    client_origin: str = "http://localhost:5173"
    password_concurrency: int = Field(default=4, ge=1, le=16)
