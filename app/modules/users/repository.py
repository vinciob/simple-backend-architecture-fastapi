"""Repository for managing user-related database operations."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    """Repository for managing user-related database operations."""

    def __init__(self, database: AsyncSession) -> None:
        self.database = database

    async def create(self, user: User) -> User:
        """Create a new user in the database."""
        self.database.add(user)
        await self.database.commit()
        return user

    async def by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address."""
        return (await self.database.scalars(select(User).where(User.email == email))).one_or_none()

    async def by_id(self, user_id: str) -> User | None:
        """Retrieve a user by their ID."""
        return await self.database.get(User, user_id)
