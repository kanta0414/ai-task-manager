from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.enums import NotificationKind, TaskStatus
from app.models.notification import Notification
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskSearchParams
from app.services.user_service import list_users

#: 予定の何分前に通知するか
REMINDER_LEAD_MINUTES = 30
WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


class NotificationService:
    """通知の作成と参照。

    定期実行（Celery）から呼ばれる処理もここに置き、
    **タスク側は薄いラッパーにとどめる**（ブローカー無しでもテストできるように）。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NotificationRepository(db)
        self.events = EventRepository(db)
        self.tasks = TaskRepository(db)

    # ------------------------------------------------------------ 参照・更新

    def list_for_user(self, user: User, *, unread_only: bool = False) -> list[Notification]:
        return self.repo.list_for_user(user.id, unread_only=unread_only)

    def mark_read(self, user: User, notification_id: int) -> Notification:
        notification = self.repo.get(notification_id, user.id)
        if notification is None:
            raise NotFoundError("通知", notification_id)
        if notification.read_at is None:
            notification.read_at = datetime.now(ZoneInfo("UTC"))
            self.db.commit()
            self.db.refresh(notification)
        return notification

    # ---------------------------------------------------------- 定期実行の処理

    def send_due_reminders(self, now: datetime) -> int:
        """まもなく始まる予定を通知する（予定開始の30分前）。"""
        created = 0
        until = now + timedelta(minutes=REMINDER_LEAD_MINUTES)

        for user in list_users(self.db):
            tz = self._timezone(user)
            for event in self.events.starting_between(user.id, now, until):
                local = event.start_at.astimezone(tz)
                notification = self.repo.add_unique(
                    user_id=user.id,
                    kind=NotificationKind.REMINDER,
                    title=f"まもなく開始: {event.title}",
                    body=f"{local:%H:%M} から始まります。",
                    dedup_key=f"reminder:event:{event.id}",
                )
                if notification is not None:
                    created += 1

        self.db.commit()
        return created

    def create_daily_digest(self, now: datetime) -> int:
        """その日の予定と期限を朝にまとめて通知する。"""
        created = 0

        for user in list_users(self.db):
            tz = self._timezone(user)
            local_now = now.astimezone(tz)
            day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            events = self.events.starting_between(user.id, day_start, day_end)
            tasks = self.tasks.search(
                user.id,
                TaskSearchParams(
                    statuses=[TaskStatus.TODO, TaskStatus.IN_PROGRESS],
                    due_from=day_start,
                    due_to=day_end,
                    limit=20,
                ),
            )
            if not events and not tasks:
                continue

            lines = []
            if events:
                lines.append("予定:")
                lines.extend(
                    f"  {e.start_at.astimezone(tz):%H:%M} {e.title}" for e in events
                )
            if tasks:
                lines.append("今日が期限のタスク:")
                lines.extend(f"  {t.title}" for t in tasks)

            notification = self.repo.add_unique(
                user_id=user.id,
                kind=NotificationKind.DAILY_DIGEST,
                title=f"{local_now.month}/{local_now.day}({WEEKDAYS_JA[local_now.weekday()]}) の予定",
                body="\n".join(lines),
                dedup_key=f"digest:{local_now:%Y-%m-%d}",
            )
            if notification is not None:
                created += 1

        self.db.commit()
        return created

    def flag_unfinished_work(self, now: datetime) -> int:
        """その日に終わらなかった作業を知らせる（夜の処理）。"""
        created = 0

        for user in list_users(self.db):
            tz = self._timezone(user)
            local_now = now.astimezone(tz)
            day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

            stale = [
                event
                for event in self.events.past_events_of_unfinished_tasks(user.id, now)
                if event.end_at >= day_start
            ]
            if not stale:
                continue

            titles = sorted({event.title for event in stale})
            notification = self.repo.add_unique(
                user_id=user.id,
                kind=NotificationKind.UNFINISHED,
                title=f"終わらなかった作業が{len(titles)}件あります",
                body="\n".join(f"  {title}" for title in titles)
                + "\n\nAIに「やり残しを明日以降に再配置して」と頼めます。",
                dedup_key=f"unfinished:{local_now:%Y-%m-%d}",
            )
            if notification is not None:
                created += 1

        self.db.commit()
        return created

    @staticmethod
    def _timezone(user: User) -> ZoneInfo:
        return ZoneInfo(user.timezone or get_settings().timezone)
