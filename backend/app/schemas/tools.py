"""LLM Tool の引数スキーマ。

LLM の出力は信用せず、必ずここで型・日時・範囲を検証してから Service へ渡す
（要件定義書 32.3）。description は LLM が引数を組み立てる際の唯一の手がかりに
なるため、日時の書式まで明記する。
"""

from pydantic import BaseModel, Field

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.common import AwareDatetime

DATETIME_HINT = "日本時間で 'YYYY-MM-DDTHH:MM' 形式（例: 2026-09-30T23:59）"


class CreateTaskArgs(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="タスクのタイトル")
    description: str | None = Field(default=None, description="補足説明")
    due_date: AwareDatetime | None = Field(default=None, description=f"期限。{DATETIME_HINT}")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="優先度")
    estimated_minutes: int | None = Field(
        default=None, gt=0, le=1440, description="所要時間（分）"
    )


class GetTaskArgs(BaseModel):
    task_id: int = Field(gt=0, description="タスクID")


class SearchTasksArgs(BaseModel):
    keyword: str | None = Field(
        default=None, max_length=200, description="タイトル・説明に含まれる語"
    )
    statuses: list[TaskStatus] | None = Field(
        default=None, description="状態での絞り込み。省略すると全状態が対象"
    )
    priorities: list[TaskPriority] | None = Field(
        default=None, description="優先度での絞り込み"
    )
    due_from: AwareDatetime | None = Field(
        default=None, description=f"この日時以降の期限。{DATETIME_HINT}"
    )
    due_to: AwareDatetime | None = Field(
        default=None, description=f"この日時までの期限。{DATETIME_HINT}"
    )
    limit: int = Field(default=20, ge=1, le=100, description="最大件数")


class UpdateTaskArgs(BaseModel):
    task_id: int = Field(gt=0, description="変更するタスクのID")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_date: AwareDatetime | None = Field(default=None, description=f"新しい期限。{DATETIME_HINT}")
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    estimated_minutes: int | None = Field(default=None, gt=0, le=1440)


class CompleteTaskArgs(BaseModel):
    task_id: int = Field(gt=0, description="完了にするタスクのID")


class DeleteTaskArgs(BaseModel):
    task_id: int = Field(gt=0, description="削除するタスクのID")
