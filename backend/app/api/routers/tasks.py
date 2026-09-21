from datetime import UTC, datetime

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, ScheduleServiceDep, TaskServiceDep
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.schemas.common import AwareDatetime
from app.schemas.schedule import ScheduledItemRead
from app.schemas.task import (
    SortOrder,
    TaskCreate,
    TaskRead,
    TaskSearchParams,
    TaskSortField,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate, user: CurrentUser, service: TaskServiceDep
) -> Task:
    """タスクを作成する。"""
    return service.create(user, payload)


@router.get("", response_model=list[TaskRead])
def search_tasks(
    user: CurrentUser,
    service: TaskServiceDep,
    status_: list[TaskStatus] | None = Query(default=None, alias="status"),
    priority: list[TaskPriority] | None = Query(default=None),
    keyword: str | None = Query(default=None, description="タイトル・説明の部分一致"),
    due_from: AwareDatetime | None = None,
    due_to: AwareDatetime | None = None,
    sort_by: TaskSortField = TaskSortField.DUE_DATE,
    order: SortOrder = SortOrder.ASC,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Task]:
    """条件でタスクを検索する。期限なしは常に末尾に並ぶ。"""
    params = TaskSearchParams(
        statuses=status_,
        priorities=priority,
        keyword=keyword,
        due_from=due_from,
        due_to=due_to,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )
    return service.search(user, params)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, user: CurrentUser, service: TaskServiceDep) -> Task:
    """タスクを1件取得する。"""
    return service.get(user, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int, payload: TaskUpdate, user: CurrentUser, service: TaskServiceDep
) -> Task:
    """タスクを部分更新する。未指定の項目は変更しない。"""
    return service.update(user, task_id, payload)


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, user: CurrentUser, service: TaskServiceDep) -> Task:
    """タスクを完了にする。"""
    return service.complete(user, task_id)


@router.post("/{task_id}/reopen", response_model=TaskRead)
def reopen_task(task_id: int, user: CurrentUser, service: TaskServiceDep) -> Task:
    """完了したタスクを未完了に戻す。"""
    return service.reopen(user, task_id)


@router.post("/{task_id}/schedule", response_model=ScheduledItemRead)
def reserve_time(
    task_id: int, user: CurrentUser, service: ScheduleServiceDep
) -> ScheduledItemRead:
    """このタスクの作業時間を空き時間に確保し、予定として登録する。"""
    item = service.reserve_time_for_task(user, task_id, now=datetime.now(UTC))
    return ScheduledItemRead(
        task_id=item.task_id,
        title=item.title,
        start_at=item.start_at,
        end_at=item.end_at,
        minutes=item.minutes,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: CurrentUser, service: TaskServiceDep) -> None:
    """タスクを削除する。"""
    service.delete(user, task_id)
