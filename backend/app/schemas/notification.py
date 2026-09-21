from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationKind


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: NotificationKind
    title: str
    body: str | None
    read_at: datetime | None
    created_at: datetime
