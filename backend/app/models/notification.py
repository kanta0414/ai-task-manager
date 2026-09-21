from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import NotificationKind

if TYPE_CHECKING:
    from app.models.user import User


class Notification(TimestampMixin, Base):
    """バックグラウンド処理が作る通知。

    配信手段（メール・LINE など）は第3段階。まずはDBに積み、UIで表示する。
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[NotificationKind] = mapped_column(
        SAEnum(
            NotificationKind,
            name="notification_kind",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)

    # 定期実行が重複して通知を作らないための鍵（例: "reminder:event:12"）
    dedup_key: Mapped[str] = mapped_column(String(120), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_notifications_user_dedup"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification id={self.id} kind={self.kind} title={self.title!r}>"
