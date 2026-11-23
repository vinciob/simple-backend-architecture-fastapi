"""Task service for handling task creation, retrieval, updating, and deletion."""

from datetime import UTC, datetime

from app.core.errors import AppError
from app.core.identifiers import new_id
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import CreateTask, TaskListItem, TaskResponse, UpdateTask


def to_task(task: Task | None) -> TaskResponse:
    """Convert a Task model instance to a TaskResponse schema. Raise an error if the task is not found."""
    if task is None:
        raise AppError(404, "Task not found")
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        status=task.status,
        due_date=task.due_date,
        created_at=task.created_at,
        updated_at=task.updated_at,
        created_by=task.created_by,
    )


class TaskService:
    """Service for managing tasks, including creation, retrieval, updating, and deletion."""
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    async def create(self, user_id: str, data: CreateTask) -> TaskResponse:
        """Create a new task for the given user and return the created task."""
        now = datetime.now(UTC)
        return to_task(
            await self.repository.create(
                Task(
                    **data.model_dump(),
                    id=new_id(),
                    created_by=user_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        )

    async def list(self, user_id: str, limit: int, before: str | None) -> list[TaskListItem]:
        """List tasks for the given user with pagination support."""
        return await self.repository.list(user_id, limit, before)

    async def get(self, task_id: str, user_id: str) -> TaskResponse:
        """Retrieve a specific task for the given user by task ID."""
        return to_task(await self.repository.get(task_id, user_id))

    async def update(self, task_id: str, user_id: str, data: UpdateTask) -> TaskResponse:
        """Update a specific task for the given user and return the updated task.
        Explicit null clears nullable fields; omitted fields stay unchanged.
        """
        return to_task(
            await self.repository.update(task_id, user_id, data.model_dump(exclude_unset=True))
        )

    async def delete(self, task_id: str, user_id: str) -> None:
        """Delete a specific task for the given user. Raise an error if not found."""
        if not await self.repository.delete(task_id, user_id):
            raise AppError(404, "Task not found")
