from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.calendar_event import CalendarEvent
from app.models.enums import TaskStatus
from app.models.task import Task
from app.schemas.event import EventSearchParams
from app.schemas.task import SortOrder


class EventRepository:
    """カレンダー予定の永続化のみを担当する。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, event: CalendarEvent) -> CalendarEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def get(self, event_id: int, user_id: int) -> CalendarEvent | None:
        stmt = select(CalendarEvent).where(
            CalendarEvent.id == event_id, CalendarEvent.user_id == user_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def search(self, user_id: int, params: EventSearchParams) -> list[CalendarEvent]:
        stmt = select(CalendarEvent).where(CalendarEvent.user_id == user_id)

        # 期間と少しでも重なる予定を対象にする（start < to かつ end > from）
        if params.to is not None:
            stmt = stmt.where(CalendarEvent.start_at < params.to)
        if params.from_ is not None:
            stmt = stmt.where(CalendarEvent.end_at > params.from_)

        if params.keyword:
            pattern = f"%{params.keyword}%"
            stmt = stmt.where(
                or_(
                    CalendarEvent.title.ilike(pattern),
                    CalendarEvent.description.ilike(pattern),
                )
            )
        if params.task_id is not None:
            stmt = stmt.where(CalendarEvent.task_id == params.task_id)

        direction = (
            CalendarEvent.start_at.asc()
            if params.order is SortOrder.ASC
            else CalendarEvent.start_at.desc()
        )
        stmt = stmt.order_by(direction, CalendarEvent.id.asc())
        stmt = stmt.limit(params.limit).offset(params.offset)
        return list(self.db.execute(stmt).scalars().all())

    def past_events_of_unfinished_tasks(
        self, user_id: int, before: datetime
    ) -> list[CalendarEvent]:
        """終わった時刻を過ぎたのに、紐づくタスクが未完了のままの予定。

        「今日終わらなかった作業」を拾うために使う。
        """
        stmt = (
            select(CalendarEvent)
            .join(Task, CalendarEvent.task_id == Task.id)
            .where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.end_at <= before,
                Task.status != TaskStatus.DONE,
            )
            .order_by(CalendarEvent.start_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete(self, event: CalendarEvent) -> None:
        self.db.delete(event)
        self.db.flush()
