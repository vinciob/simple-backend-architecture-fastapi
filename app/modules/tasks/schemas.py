"""Schemas for task-related operations."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BeforeValidator, Field, model_validator

from app.core.schemas import APIModel

TaskStatus = Literal["created", "in_progress", "completed"]
TaskName = Annotated[
    str,
    BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
    Field(min_length=1, max_length=120),
]
Description = Annotated[str, Field(max_length=2000)]


class CreateTask(APIModel):
    """Schema for creating a new task."""
    name: TaskName
    description: Description | None = None
    status: TaskStatus = "created"
    due_date: AwareDatetime | None = None


class UpdateTask(APIModel):
    """Schema for updating an existing task."""
    name: TaskName | None = None
    description: Description | None = None
    status: TaskStatus | None = None
    due_date: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        """Validate that at least one field is provided and required fields are not null."""
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        for field in ("name", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TaskResponse(APIModel):
    """Schema for task response."""
    id: str
    name: str
    description: str | None
    status: TaskStatus
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: str


class TaskListItem(APIModel):
    """Schema for task list item."""
    id: str = Field(serialization_alias="_id")
    name: str
    due_date: datetime | None
    status: TaskStatus
