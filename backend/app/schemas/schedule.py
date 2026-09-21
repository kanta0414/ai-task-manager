from datetime import datetime

from pydantic import BaseModel

from app.services.schedule_service import FreeSlot, SchedulePlan


class FreeSlotRead(BaseModel):
    start_at: datetime
    end_at: datetime
    minutes: int

    @classmethod
    def from_slot(cls, slot: FreeSlot) -> "FreeSlotRead":
        return cls(start_at=slot.start_at, end_at=slot.end_at, minutes=slot.minutes)


class FreeTimeResponse(BaseModel):
    #: 適用した制約（何時〜何時を探したか）
    rule: str
    count: int
    slots: list[FreeSlotRead]


class ScheduledItemRead(BaseModel):
    task_id: int
    title: str
    start_at: datetime
    end_at: datetime
    minutes: int


class SkippedTaskRead(BaseModel):
    task_id: int
    title: str
    reason: str


class SchedulePlanResponse(BaseModel):
    """スケジュール案。登録は別途の承認が必要。"""

    rule: str
    items: list[ScheduledItemRead]
    skipped: list[SkippedTaskRead]

    @classmethod
    def from_plan(cls, plan: SchedulePlan) -> "SchedulePlanResponse":
        return cls(
            rule=plan.rule,
            items=[
                ScheduledItemRead(
                    task_id=item.task_id,
                    title=item.title,
                    start_at=item.start_at,
                    end_at=item.end_at,
                    minutes=item.minutes,
                )
                for item in plan.items
            ],
            skipped=[
                SkippedTaskRead(task_id=s.task_id, title=s.title, reason=s.reason)
                for s in plan.skipped
            ],
        )
