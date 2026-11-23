"""Authentication routes for handling login, refresh, and logout operations."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_database
from app.core.errors import AppError
from app.core.security import Security, get_security
from app.modules.auth.repository import SessionRepository
from app.modules.auth.schemas import LoginInput, TokenResponse
from app.modules.auth.service import AuthResult, AuthService
from app.modules.users.repository import UserRepository

REFRESH_COOKIE_NAME = "refreshToken"

def check_origin(request: Request, security: Annotated[Security, Depends(get_security)]) -> None:
    """Cookie endpoints accept only the configured browser origin; CLI clients may omit Origin."""
    origin = request.headers.get("origin")
    if origin is not None and origin != security.settings.client_origin:
        raise AppError(403, "Origin not allowed")

# Initialize the authentication router with the appropriate prefix, tags, and dependencies.
router = APIRouter(prefix="/auth", tags=["Auth"], dependencies=[Depends(check_origin)])


def get_service(
    database: Annotated[AsyncSession, Depends(get_database)],
    security: Annotated[Security, Depends(get_security)],
) -> AuthService:
    """Create an instance of AuthService with the necessary repositories and security."""
    return AuthService(UserRepository(database), SessionRepository(database), security)


def send_tokens(response: Response, result: AuthResult, security: Security) -> TokenResponse:
    """Send authentication tokens to the client via cookies and return the access token."""
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        result.refresh_token,
        httponly=True,
        secure=security.settings.environment == "production",
        samesite="lax",
        path="/auth",
        max_age=max(0, int((result.expires_at - datetime.now(UTC)).total_seconds())),
    )
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=result.access_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginInput,
    response: Response,
    service: Annotated[AuthService, Depends(get_service)],
    security: Annotated[Security, Depends(get_security)],
) -> TokenResponse:
    """Handle user login and return authentication tokens."""
    return send_tokens(response, await service.login(data), security)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_service)],
    security: Annotated[Security, Depends(get_security)],
) -> TokenResponse:
    """Handle refresh token requests and return new authentication tokens."""
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise AppError(401, "Refresh token missing")
    return send_tokens(response, await service.refresh(token), security)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    service: Annotated[AuthService, Depends(get_service)],
    security: Annotated[Security, Depends(get_security)],
) -> Response:
    """Handle user logout by invalidating the refresh token and clearing the cookie."""
    await service.logout(request.cookies.get(REFRESH_COOKIE_NAME))
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path="/auth",
        httponly=True,
        samesite="lax",
        secure=security.settings.environment == "production",
    )
    return response
