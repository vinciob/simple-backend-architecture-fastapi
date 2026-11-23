from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.tasks.schemas import TaskStatus


class Task(Base):
    """Task table.

    Stores information about tasks, including their name, description, status,
    due date, and the user who created them. Inherits created_at and updated_at
    timestamps from the base class.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('created', 'in_progress', 'completed')", name="ck_task_status"),
        Index("ix_tasks_owner_id", "created_by", "id"),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[TaskStatus] = mapped_column(String(20))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
