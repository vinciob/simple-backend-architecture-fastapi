"""A pool per worker and an isolated AsyncSession per request."""

from datetime import datetime
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime

from app.core.config import DatabaseSettings


class Base(DeclarativeBase):
    """Base class for all declarative models.

    All ORM models should inherit from this class to ensure consistent
    metadata and table definitions.
    """

    # created_at and update_at
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create an async engine with a connection pool based on the provided settings."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=0,
        pool_timeout=3,
        pool_pre_ping=True,
        connect_args={
            "timeout": 3,
            "command_timeout": 5,
            "server_settings": {"statement_timeout": "5000"},
        },
    )


async def get_database(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide an async database session for the current request."""
    # Repositories commit complete write units explicitly. Closing rolls back unfinished work.
    async with request.app.state.session_factory() as session:
        yield session
