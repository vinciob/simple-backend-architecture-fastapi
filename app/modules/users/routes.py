"""User routes for handling registration and retrieval of user information."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_database
from app.core.security import Security, UserId, get_security
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import RegisterInput, RegisterResponse, UserResponse
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def get_service(
    database: Annotated[AsyncSession, Depends(get_database)],
    security: Annotated[Security, Depends(get_security)],
) -> UserService:
    """Create an instance of UserService with the necessary repository and security."""
    return UserService(UserRepository(database), security)


@router.post("", status_code=201, response_model=RegisterResponse)
async def register(
    data: RegisterInput, service: Annotated[UserService, Depends(get_service)]
) -> RegisterResponse:
    """Handle user registration and return the registered user's information."""
    return RegisterResponse(user=await service.register(data))


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: UserId, service: Annotated[UserService, Depends(get_service)]
) -> UserResponse:
    """Retrieve the current user's information based on their user ID."""
    return await service.me(user_id)
