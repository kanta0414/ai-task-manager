from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MAX_DESCRIPTION, AwareDatetime
from app.schemas.task import SortOrder


class EventCreate(BaseModel):
    """予定作成の入力。end_at > start_at の検証は Service Layer で行う。"""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    start_at: AwareDatetime
    end_at: AwareDatetime
    location: str | None = Field(default=None, max_length=255)
    # タスクの作業時間として予定を作る場合に紐づける
    task_id: int | None = None


class EventUpdate(BaseModel):
    """部分更新。未指定の項目は変更しない。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    location: str | None = Field(default=None, max_length=255)
    task_id: int | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    location: str | None
    task_id: int | None
    created_at: datetime
    updated_at: datetime


class EventSearchParams(BaseModel):
    """期間検索。カレンダー表示と find_free_time の両方で使う。"""

    # 指定期間に「少しでも重なる」予定を返す（またぎの予定を落とさないため）
    from_: AwareDatetime | None = None
    to: AwareDatetime | None = None
    keyword: str | None = Field(default=None, max_length=200)
    task_id: int | None = None
    order: SortOrder = SortOrder.ASC
    limit: int = Field(default=500, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
