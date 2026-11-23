"""Repository for managing task-related database operations."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskListItem


class TaskRepository:
    """Repository for managing task-related database operations."""

    def __init__(self, database: AsyncSession) -> None:
        self.database = database

    async def create(self, task: Task) -> Task:
        """Create a new task in the database."""
        self.database.add(task)
        await self.database.commit()
        return task

    async def list(self, user_id: str, limit: int, before: str | None) -> list[TaskListItem]:
        """List tasks for a given user, with optional pagination."""
        query = select(Task.id, Task.name, Task.due_date, Task.status).where(
            Task.created_by == user_id
        )
        if before:
            query = query.where(Task.id < before.lower())
        rows = await self.database.execute(query.order_by(Task.id.desc()).limit(limit))
        return [
            TaskListItem(id=r.id, name=r.name, due_date=r.due_date, status=r.status) for r in rows
        ]

    async def get(self, task_id: str, user_id: str) -> Task | None:
        """Retrieve a task by its ID for a given user."""
        return (
            await self.database.scalars(
                select(Task).where(Task.id == task_id.lower(), Task.created_by == user_id)
            )
        ).one_or_none()

    async def update(self, task_id: str, user_id: str, changes: dict[str, Any]) -> Task | None:
        """Update a task for a given user with the provided changes."""
        result = await self.database.scalar(
            update(Task)
            .where(Task.id == task_id.lower(), Task.created_by == user_id)
            .values(**changes, updated_at=datetime.now(UTC))
            .returning(Task)
        )
        await self.database.commit()
        return result

    async def delete(self, task_id: str, user_id: str) -> bool:
        """Delete a task by its ID for a given user."""
        deleted_id = await self.database.scalar(
            delete(Task)
            .where(Task.id == task_id.lower(), Task.created_by == user_id)
            .returning(Task.id)
        )
        await self.database.commit()
        return deleted_id is not None
