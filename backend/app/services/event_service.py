from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.calendar_event import CalendarEvent
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.event import EventCreate, EventSearchParams, EventUpdate

# 1件の予定として許容する最大の長さ（誤入力・LLM の誤生成を弾く）
MAX_EVENT_HOURS = 24


class EventService:
    """カレンダー予定の業務ロジック。

    通常UI(router) と LLM Tool は **どちらもこのクラスを経由する**。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EventRepository(db)
        self.tasks = TaskRepository(db)

    def create(self, user: User, data: EventCreate) -> CalendarEvent:
        self._validate_period(data.start_at, data.end_at)
        if data.task_id is not None:
            self._ensure_task_owned(user, data.task_id)

        event = CalendarEvent(user_id=user.id, **data.model_dump())
        self.repo.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get(self, user: User, event_id: int) -> CalendarEvent:
        event = self.repo.get(event_id, user.id)
        if event is None:
            raise NotFoundError("予定", event_id)
        return event

    def search(self, user: User, params: EventSearchParams) -> list[CalendarEvent]:
        return self.repo.search(user.id, params)

    def update(self, user: User, event_id: int, data: EventUpdate) -> CalendarEvent:
        event = self.get(user, event_id)
        changes = data.model_dump(exclude_unset=True)

        # 片方だけ変更された場合も、変更後の組み合わせで検証する
        start_at = changes.get("start_at", event.start_at)
        end_at = changes.get("end_at", event.end_at)
        self._validate_period(start_at, end_at)

        if changes.get("task_id") is not None:
            self._ensure_task_owned(user, changes["task_id"])

        for field, value in changes.items():
            setattr(event, field, value)

        self.db.commit()
        self.db.refresh(event)
        return event

    def delete(self, user: User, event_id: int) -> None:
        event = self.get(user, event_id)
        self.repo.delete(event)
        self.db.commit()

    @staticmethod
    def _validate_period(start_at: datetime, end_at: datetime) -> None:
        if end_at <= start_at:
            raise BusinessRuleError("終了時刻は開始時刻より後にしてください")
        if (end_at - start_at).total_seconds() > MAX_EVENT_HOURS * 3600:
            raise BusinessRuleError(
                f"1件の予定は最大 {MAX_EVENT_HOURS} 時間までです"
            )

    def _ensure_task_owned(self, user: User, task_id: int) -> None:
        """他ユーザーのタスクに予定を紐づけられないようにする。"""
        if self.tasks.get(task_id, user.id) is None:
            raise NotFoundError("タスク", task_id)
