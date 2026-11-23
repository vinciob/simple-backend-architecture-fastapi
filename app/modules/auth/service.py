"""Authentication service for handling login, refresh, and logout operations."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.errors import AppError
from app.core.identifiers import new_id
from app.core.security import (
    Security,
    generate_refresh_token,
    hash_refresh_token,
    parse_refresh_token,
)
from app.modules.auth.models import Session
from app.modules.auth.repository import SessionRepository
from app.modules.auth.schemas import LoginInput
from app.modules.users.repository import UserRepository


@dataclass(frozen=True)
class AuthResult:
    """Result of an authentication operation."""
    access_token: str
    refresh_token: str
    expires_at: datetime


class AuthService:
    """Service for handling authentication operations."""
    def __init__(
        self, users: UserRepository, sessions: SessionRepository, security: Security
    ) -> None:
        self.users = users
        self.sessions = sessions
        self.security = security

    async def login(self, data: LoginInput) -> AuthResult:
        """Authenticate a user and create a new session."""

        # Retrieve the user by email.
        user = await self.users.by_email(str(data.email))

        # Verify a dummy hash as well to reduce user-enumeration timing differences.
        password_hash = user.password_hash if user else self.security.dummy_hash
        valid = await self.security.verify_password(data.password, password_hash)
        if user is None or not valid:
            raise AppError(401, "Invalid credentials")

        # Create a new session for the authenticated user.
        now = datetime.now(UTC)
        session_id = new_id()
        token = generate_refresh_token(session_id)
        expires_at = now + timedelta(seconds=self.security.settings.refresh_token_ttl)
        await self.sessions.create(
            Session(
                id=session_id,
                user_id=user.id,
                refresh_token_hash=hash_refresh_token(token),
                created_at=now,
                last_used_at=now,
                expires_at=expires_at,
                revoked_at=None,
            )
        )

        return AuthResult(self.security.access_token(user.id, session_id), token, expires_at)

    async def refresh(self, token: str) -> AuthResult:
        """Refresh an existing session using a refresh token."""

        # Parse the refresh token to extract the session ID and token hash.
        session_id, token_hash = parse_refresh_token(token)

        # Generate the next refresh token for the session.
        next_token = generate_refresh_token(session_id)

        # Rotate the session with the new refresh token.
        session = await self.sessions.rotate(session_id, token_hash, hash_refresh_token(next_token))
        if session is None:
            await self.sessions.revoke_reused(session_id, token_hash)
            raise AppError(401, "Invalid refresh token")
        if await self.users.by_id(session.user_id) is None:
            await self.sessions.revoke(session_id, hash_refresh_token(next_token))
            raise AppError(401, "Invalid refresh token")

        return AuthResult(
            self.security.access_token(session.user_id, session_id), next_token, session.expires_at
        )

    async def logout(self, token: str | None) -> None:
        """Logout a user by revoking the session associated with the refresh token."""
        if token:
            try:
                session_id, token_hash = parse_refresh_token(token)
            except AppError:
                return  # Logout remains idempotent even with a malformed cookie.

            # Revoke the session associated with the refresh token.
            await self.sessions.revoke(session_id, token_hash)
