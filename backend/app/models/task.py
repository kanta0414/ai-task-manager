from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import TaskPriority, TaskStatus

if TYPE_CHECKING:
    from app.models.calendar_event import CalendarEvent
    from app.models.user import User


class Task(TimestampMixin, Base):
    """タスク。通常UIとLLM Tool の両方から同じレコードを操作する。"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(
            TaskStatus,
            name="task_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(
            TaskPriority,
            name="task_priority",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
    )

    # 期限。時刻指定の締切にも対応できるよう timezone-aware な日時で保持する
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 所要時間（分）。自動スケジューリングで必要な作業時間として使う
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="tasks")
    events: Mapped[list["CalendarEvent"]] = relationship(back_populates="task")

    __table_args__ = (
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="ck_tasks_estimated_minutes_positive",
        ),
        # 「今週締切のタスク」「未完了タスク」の検索を想定した複合インデックス
        Index("ix_tasks_user_id_status", "user_id", "status"),
        Index("ix_tasks_user_id_due_date", "user_id", "due_date"),
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"
