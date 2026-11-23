"""Repository for managing session-related database operations."""

from datetime import UTC, datetime

from sqlalchemy import exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Exists

from app.modules.auth.models import Session, UsedRefreshToken


class SessionRepository:
    """Repository for managing session-related database operations.

    Provides methods for creating, rotating, and revoking sessions, as well as
    checking for reused refresh tokens.
    """

    def __init__(self, database: AsyncSession) -> None:
        self.database = database

    async def create(self, session: Session) -> None:
        """Create a new session in the database."""
        self.database.add(session)
        await self.database.commit()

    async def rotate(self, session_id: str, old_hash: str, new_hash: str) -> Session | None:
        """Rotate the refresh token for an existing session.

        Updates the session with a new refresh token hash and records the old hash
        in the used refresh token history.

        Returns the updated session if successful, or None if the session could not be rotated.
        """
        now = datetime.now(UTC)
        # PostgreSQL rechecks this predicate after waiting for a competing UPDATE.
        session = await self.database.scalar(
            update(Session)
            .where(
                Session.id == session_id,
                Session.refresh_token_hash == old_hash,
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
            .values(refresh_token_hash=new_hash, last_used_at=now)
            .returning(Session)
        )
        if session is not None:
            self.database.add(UsedRefreshToken(token_hash=old_hash, session_id=session_id))

        # Rotation and replay history become visible together, even under concurrent refreshes.
        await self.database.commit()
        return session

    def _was_used(self, session_id: str, token_hash: str) -> Exists:
        """Check if a refresh token has already been used for a given session.

        Returns an SQLAlchemy Exists object that can be used in a query.
        """
        return exists(
            select(UsedRefreshToken.token_hash).where(
                UsedRefreshToken.session_id == session_id, UsedRefreshToken.token_hash == token_hash
            )
        )

    async def revoke_reused(self, session_id: str, token_hash: str) -> None:
        """Revoke a session if a reused refresh token is detected.

        This method marks the session as revoked if the provided token has already been used.
        Ensures that replay attacks are mitigated by revoking the session before raising an error.
        """
        await self.database.execute(
            update(Session)
            .where(
                Session.id == session_id,
                Session.revoked_at.is_(None),
                self._was_used(session_id, token_hash),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        # Commit before the service raises 401: rollback must not undo replay revocation.
        await self.database.commit()

    async def revoke(self, session_id: str, token_hash: str) -> None:
        """Revoke a session for a given session ID and token hash.

        Marks the session as revoked if it is active and the provided token matches
        either the current refresh token or has been used previously.
        """
        await self.database.execute(
            update(Session)
            .where(
                Session.id == session_id,
                Session.revoked_at.is_(None),
                or_(
                    Session.refresh_token_hash == token_hash, self._was_used(session_id, token_hash)
                ),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self.database.commit()
