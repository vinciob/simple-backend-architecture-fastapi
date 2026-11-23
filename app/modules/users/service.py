"""User service for handling registration and user retrieval operations."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.core.identifiers import new_id
from app.core.security import Security
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import RegisterInput, UserResponse


def to_user(user: User) -> UserResponse:
    """Convert a User model instance to a UserResponse schema."""
    return UserResponse(id=user.id, name=user.name, email=user.email, created_at=user.created_at)

class UserService:
    """Service for handling user-related operations such as registration and retrieval."""

    def __init__(self, repository: UserRepository, security: Security) -> None:
        self.repository = repository
        self.security = security

    async def register(self, data: RegisterInput) -> UserResponse:
        """Register a new user and return the corresponding UserResponse."""
        now = datetime.now(UTC)
        user = User(
            id=new_id(),
            name=data.name,
            email=str(data.email),
            password_hash=await self.security.hash_password(data.password),
            created_at=now,
            updated_at=now,
        )
        try:
            return to_user(await self.repository.create(user))
        except IntegrityError as error:
            await self.repository.database.rollback()
            # Unique constraints also cover concurrent registration requests.
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise AppError(409, "Email already registered") from None
            raise

    async def me(self, user_id: str) -> UserResponse:
        """Retrieve the current user's information by their user ID."""
        user = await self.repository.by_id(user_id)
        if user is None:
            raise AppError(404, "User not found")
        return to_user(user)
