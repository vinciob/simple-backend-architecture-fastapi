"""JWT authentication is stateless; Argon2 work has a bounded thread budget."""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import anyio
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.errors import AppError


bearer = HTTPBearer(auto_error=False)


class Security:
    """Security utilities for password hashing and JWT handling."""
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
        self.limiter = anyio.CapacityLimiter(settings.password_concurrency)
        self.dummy_hash = ""

    async def hash_password(self, password: str) -> str:
        """Hash the given password"""
        return await anyio.to_thread.run_sync(self.hasher.hash, password, limiter=self.limiter)

    async def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify the given password against the stored hash."""
        def verify() -> bool:
            try:
                return self.hasher.verify(password_hash, password)
            except (VerificationError, InvalidHashError):
                return False

        return await anyio.to_thread.run_sync(verify, limiter=self.limiter)

    def access_token(self, user_id: str, session_id: str) -> str:
        """Generate a JWT access token for the given user and session."""
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(session_id),
                "iat": now,
                "exp": now + timedelta(seconds=self.settings.access_token_ttl),
                "iss": self.settings.jwt_issuer,
                "aud": self.settings.jwt_audience,
            },
            self.settings.jwt_secret.get_secret_value(),
            algorithm="HS256",
        )

    def decode(self, token: str) -> str:
        """Decode and validate the given JWT access token."""
        try:
            claims = jwt.decode(
                token,
                self.settings.jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                issuer=self.settings.jwt_issuer,
                audience=self.settings.jwt_audience,
                options={"require": ["sub", "sid", "exp", "iat", "iss", "aud"]},
            )
            for key in ("sub", "sid"):
                if not isinstance(claims[key], str) or not re.fullmatch(
                    r"[a-f0-9]{24}", claims[key]
                ):
                    raise ValueError("Invalid identifier")
            return str(claims["sub"])
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise AppError(401, "Invalid access token") from None


def get_security(request: Request) -> Security:
    """Retrieve the security instance from the request."""
    return request.app.state.security  # type: ignore[no-any-return]


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    security: Annotated[Security, Depends(get_security)],
) -> str:
    """Retrieve the current user ID from the access token."""
    if credentials is None:
        raise AppError(401, "Invalid access token")
    return security.decode(credentials.credentials)


UserId = Annotated[str, Depends(current_user)]


def generate_refresh_token(session_id: str) -> str:
    """Generate a secure refresh token for the given session ID."""
    return f"{session_id}.{secrets.token_hex(32)}"


def hash_refresh_token(token: str) -> str:
    """Hash the given refresh token using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def parse_refresh_token(token: str) -> tuple[str, str]:
    """Parse and validate the given refresh token, returning the session ID and hashed token."""
    if not re.fullmatch(r"[a-f0-9]{24}\.[a-f0-9]{64}", token):
        raise AppError(401, "Invalid refresh token")
    return token[:24], hash_refresh_token(token)
