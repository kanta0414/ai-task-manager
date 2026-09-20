from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import SortOrder, TaskSearchParams, TaskSortField


class TaskRepository:
    """タスクの永続化のみを担当する。業務ルールは Service Layer に置く。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, task: Task) -> Task:
        self.db.add(task)
        self.db.flush()
        return task

    def get(self, task_id: int, user_id: int) -> Task | None:
        """他ユーザーのタスクを取得できないよう user_id を必ず条件に入れる。"""
        stmt = select(Task).where(Task.id == task_id, Task.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def search(self, user_id: int, params: TaskSearchParams) -> list[Task]:
        stmt = select(Task).where(Task.user_id == user_id)

        if params.statuses:
            stmt = stmt.where(Task.status.in_(params.statuses))
        if params.priorities:
            stmt = stmt.where(Task.priority.in_(params.priorities))
        if params.keyword:
            pattern = f"%{params.keyword}%"
            stmt = stmt.where(
                or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
            )
        if params.due_from is not None:
            stmt = stmt.where(Task.due_date >= params.due_from)
        if params.due_to is not None:
            stmt = stmt.where(Task.due_date <= params.due_to)

        column = {
            TaskSortField.DUE_DATE: Task.due_date,
            # ENUM は low < medium < high の定義順で並ぶため desc で高優先度が先頭
            TaskSortField.PRIORITY: Task.priority,
            TaskSortField.CREATED_AT: Task.created_at,
            TaskSortField.TITLE: Task.title,
        }[params.sort_by]
        direction = column.asc() if params.order is SortOrder.ASC else column.desc()
        # 期限なしのタスクは常に末尾へ
        stmt = stmt.order_by(direction.nulls_last(), Task.id.asc())

        stmt = stmt.limit(params.limit).offset(params.offset)
        return list(self.db.execute(stmt).scalars().all())

    def delete(self, task: Task) -> None:
        self.db.delete(task)
        self.db.flush()
