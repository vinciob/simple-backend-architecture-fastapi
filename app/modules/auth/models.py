"""Authentication-related database models.

Defines the database schema for user sessions and used refresh tokens,
including relationships and constraints to ensure data integrity and
prevent replay attacks.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Session(Base):
    """User session table.

    Stores information about active user sessions, including refresh token hashes,
    creation and last used timestamps, expiration, and revocation status.
    """
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_expires_at", "expires_at"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsedRefreshToken(Base):
    """Replay history in its own table, removed by cascading session deletion.

    Stores hashes of used refresh tokens to prevent reuse after they have been
    invalidated or the associated session has been revoked.
    """

    __tablename__ = "used_refresh_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Relationships
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
