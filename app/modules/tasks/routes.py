"""Task routes for handling task-related API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_database
from app.core.schemas import Identifier
from app.core.security import UserId
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import CreateTask, TaskListItem, TaskResponse, UpdateTask
from app.modules.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_service(database: Annotated[AsyncSession, Depends(get_database)]) -> TaskService:
    """Create an instance of TaskService with the necessary repository."""
    return TaskService(TaskRepository(database))


Service = Annotated[TaskService, Depends(get_service)]


@router.post("", status_code=201, response_model=TaskResponse)
async def create(data: CreateTask, user_id: UserId, service: Service) -> TaskResponse:
    """Handle the creation of a new task for the current user."""
    return await service.create(user_id, data)


@router.get("", response_model=list[TaskListItem])
async def list_tasks(
    user_id: UserId,
    service: Service,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: Annotated[Identifier | None, Query()] = None,
) -> list[TaskListItem]:
    """Handle listing tasks for the current user with pagination support."""
    items = await service.list(user_id, limit + 1, before)
    if len(items) > limit:
        response.headers["X-Next-Cursor"] = items[limit - 1].id
    return items[:limit]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: Identifier, user_id: UserId, service: Service) -> TaskResponse:
    """Handle retrieving a specific task for the current user by task ID."""
    return await service.get(task_id, user_id)

@router.patch("/{task_id}", response_model=TaskResponse)
async def update(
    task_id: Identifier, data: UpdateTask, user_id: UserId, service: Service
) -> TaskResponse:
    """Handle updating a specific task for the current user by task ID."""
    return await service.update(task_id, user_id, data)


@router.delete("/{task_id}", status_code=204)
async def delete(task_id: Identifier, user_id: UserId, service: Service) -> Response:
    """Handle deleting a specific task for the current user by task ID."""
    await service.delete(task_id, user_id)
    return Response(status_code=204)
