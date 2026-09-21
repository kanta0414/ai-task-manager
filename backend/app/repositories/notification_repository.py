from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import NotificationKind
from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_unique(
        self,
        user_id: int,
        kind: NotificationKind,
        title: str,
        body: str | None,
        dedup_key: str,
    ) -> Notification | None:
        """同じ dedup_key が既にあれば作らない。

        定期実行が何度走っても通知が増えないようにするため、
        アプリ側の判定ではなく DB の一意制約で担保する。
        """
        notification = Notification(
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            dedup_key=dedup_key,
        )
        savepoint = self.db.begin_nested()
        try:
            self.db.add(notification)
            self.db.flush()
        except IntegrityError:
            savepoint.rollback()
            return None
        return notification

    def get(self, notification_id: int, user_id: int) -> Notification | None:
        stmt = select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(
        self, user_id: int, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
