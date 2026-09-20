from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class CalendarEvent(TimestampMixin, Base):
    """カレンダー上の予定。タスクに紐づけて「作業時間」として配置できる。"""

    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))

    # タスクの作業時間として作られた予定。タスク削除時は予定を残して紐付けだけ外す
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )

    user: Mapped["User"] = relationship(back_populates="events")
    task: Mapped["Task | None"] = relationship(back_populates="events")

    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_calendar_events_end_after_start"),
        # 「9/21の予定」「今週の空き時間」の検索を想定した複合インデックス
        Index("ix_calendar_events_user_id_start_at", "user_id", "start_at"),
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent id={self.id} title={self.title!r} start_at={self.start_at}>"
