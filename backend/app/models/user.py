from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.calendar_event import CalendarEvent
    from app.models.task import Task


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # LLM が「明日の14時」を解釈する際の基準となるタイムゾーン
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Asia/Tokyo", server_default="Asia/Tokyo"
    )
    # bcrypt のハッシュ。認証導入前に作られたユーザーは未設定のことがある
    password_hash: Mapped[str | None] = mapped_column(String(255))

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
