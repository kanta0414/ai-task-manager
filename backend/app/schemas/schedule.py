from datetime import datetime

from pydantic import BaseModel

from app.services.schedule_service import FreeSlot


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
