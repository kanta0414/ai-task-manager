from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import CalendarProvider

if TYPE_CHECKING:
    from app.models.user import User


class ExternalCalendarAccount(TimestampMixin, Base):
    """連携した外部カレンダーのアカウント。

    現在は読み取り専用（空き時間の計算に外部の予定を含めるため）。
    トークンは暗号化して保存する。
    """

    __tablename__ = "external_calendar_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[CalendarProvider] = mapped_column(
        SAEnum(
            CalendarProvider,
            name="calendar_provider",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    #: 連携先のアカウント（画面に表示して、どれと繋がっているか分かるようにする）
    account_email: Mapped[str] = mapped_column(String(255), nullable=False)

    #: 暗号化済みのトークン。平文では保存しない
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    #: 更新トークンが失効し、再連携が必要な状態。
    #: テストモードの OAuth クライアントは7日で失効するため必ず起こる
    reauth_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        # 同じ提供元は1ユーザーにつき1つ
        UniqueConstraint("user_id", "provider", name="uq_external_calendar_user_provider"),
    )

    def __repr__(self) -> str:
        return f"<ExternalCalendarAccount id={self.id} provider={self.provider}>"
