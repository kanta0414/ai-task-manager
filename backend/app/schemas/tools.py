"""LLM Tool の引数スキーマ。

LLM の出力は信用せず、必ずここで型・日時・範囲を検証してから Service へ渡す
（要件定義書 32.3）。description は LLM が引数を組み立てる際の唯一の手がかりに
なるため、日時の書式まで明記する。
"""

from pydantic import BaseModel, Field

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.common import AwareDatetime

DATETIME_HINT = "例: 2026-09-30T23:59"


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


class CreateEventArgs(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="予定のタイトル")
    start_at: AwareDatetime = Field(description=f"開始日時。{DATETIME_HINT}")
    end_at: AwareDatetime = Field(description=f"終了日時。{DATETIME_HINT}")
    description: str | None = Field(default=None, description="メモ")
    location: str | None = Field(default=None, max_length=255, description="場所")
    task_id: int | None = Field(
        default=None,
        gt=0,
        description="既存タスクに紐づける場合のみ指定。分からなければ省略する",
    )


class GetEventArgs(BaseModel):
    event_id: int = Field(gt=0, description="予定ID")


class SearchEventsArgs(BaseModel):
    period_start: AwareDatetime | None = Field(
        default=None, description=f"検索する期間の開始日時。{DATETIME_HINT}"
    )
    period_end: AwareDatetime | None = Field(
        default=None, description=f"検索する期間の終了日時。{DATETIME_HINT}"
    )
    keyword: str | None = Field(
        default=None, max_length=200, description="タイトル・メモに含まれる語"
    )
    limit: int = Field(default=50, ge=1, le=200, description="最大件数")


class UpdateEventArgs(BaseModel):
    event_id: int = Field(gt=0, description="変更する予定のID")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    start_at: AwareDatetime | None = Field(
        default=None, description=f"新しい開始日時。{DATETIME_HINT}"
    )
    end_at: AwareDatetime | None = Field(
        default=None, description=f"新しい終了日時。{DATETIME_HINT}"
    )
    description: str | None = None
    location: str | None = Field(default=None, max_length=255)
    task_id: int | None = Field(default=None, gt=0)


class DeleteEventArgs(BaseModel):
    event_id: int = Field(gt=0, description="削除する予定のID")


class FindFreeTimeArgs(BaseModel):
    period_start: AwareDatetime = Field(
        description="探す期間の開始日時。その日全体を探すなら 00:00 を指定する（例: 2026-09-30T00:00）"
    )
    period_end: AwareDatetime = Field(
        description="探す期間の終了日時。その日全体なら翌日の 00:00 を指定する"
    )
    minutes_needed: int = Field(
        gt=0, le=1440, description="確保したい時間（分）"
    )
    exclude_weekends: bool = Field(default=False, description="土日を除くかどうか")


class GenerateScheduleArgs(BaseModel):
    period_start: AwareDatetime = Field(
        description="配置する期間の開始日時。その日から始めるなら 00:00（例: 2026-09-22T00:00）"
    )
    period_end: AwareDatetime = Field(
        description="配置する期間の終了日時。最終日を含めるなら翌日の 00:00"
    )
    task_ids: list[int] | None = Field(
        default=None,
        description="対象を絞る場合のタスクID。省略すると未完了タスク全体が対象",
    )
    exclude_weekends: bool = Field(default=False, description="土日を除くかどうか")


class ScheduleItemArg(BaseModel):
    """承認済みスケジュールの1件。"""

    task_id: int = Field(gt=0)
    start_at: AwareDatetime
    end_at: AwareDatetime


class ApplyScheduleArgs(BaseModel):
    """承認後に予定を登録するための引数（LLM には提示しない）。"""

    items: list[ScheduleItemArg] = Field(min_length=1, max_length=50)
