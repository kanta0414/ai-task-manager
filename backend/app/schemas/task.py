from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.common import MAX_DESCRIPTION, AwareDatetime


class TaskCreate(BaseModel):
    """タスク作成の入力。通常UI と LLM Tool の両方がこのスキーマで検証される。"""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: AwareDatetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0, le=60 * 24)
    parent_task_id: int | None = Field(
        default=None, gt=0, description="分解元のタスクID"
    )


class TaskUpdate(BaseModel):
    """部分更新。未指定の項目は変更しない（null を明示すればクリアできる）。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: AwareDatetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0, le=60 * 24)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    estimated_minutes: int | None
    completed_at: datetime | None
    parent_task_id: int | None
    created_at: datetime
    updated_at: datetime


class TaskSortField(StrEnum):
    DUE_DATE = "due_date"
    PRIORITY = "priority"
    CREATED_AT = "created_at"
    TITLE = "title"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class TaskSearchParams(BaseModel):
    """一覧・検索の条件。LLM の search_tasks Tool でもそのまま使う。"""

    statuses: list[TaskStatus] | None = None
    priorities: list[TaskPriority] | None = None
    keyword: str | None = Field(default=None, max_length=200)
    due_from: AwareDatetime | None = None
    due_to: AwareDatetime | None = None
    sort_by: TaskSortField = TaskSortField.DUE_DATE
    order: SortOrder = SortOrder.ASC
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
