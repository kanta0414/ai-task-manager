from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskSearchParams, TaskUpdate


class TaskService:
    """タスクの業務ロジック。

    通常UI(router) と LLM Tool は **どちらもこのクラスを経由する**。
    Tool 用に別のロジックを作らないこと。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TaskRepository(db)

    def create(self, user: User, data: TaskCreate) -> Task:
        task = Task(user_id=user.id, **data.model_dump())
        if task.status is TaskStatus.DONE:
            task.completed_at = datetime.now(UTC)
        self.repo.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, user: User, task_id: int) -> Task:
        task = self.repo.get(task_id, user.id)
        if task is None:
            raise NotFoundError("タスク", task_id)
        return task

    def search(self, user: User, params: TaskSearchParams) -> list[Task]:
        return self.repo.search(user.id, params)

    def update(self, user: User, task_id: int, data: TaskUpdate) -> Task:
        task = self.get(user, task_id)
        changes = data.model_dump(exclude_unset=True)

        if "status" in changes:
            self._apply_status(task, changes.pop("status"))
        for field, value in changes.items():
            setattr(task, field, value)

        self.db.commit()
        self.db.refresh(task)
        return task

    def complete(self, user: User, task_id: int) -> Task:
        task = self.get(user, task_id)
        self._apply_status(task, TaskStatus.DONE)
        self.db.commit()
        self.db.refresh(task)
        return task

    def reopen(self, user: User, task_id: int) -> Task:
        """完了したタスクを未完了へ戻す。"""
        task = self.get(user, task_id)
        self._apply_status(task, TaskStatus.TODO)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete(self, user: User, task_id: int) -> None:
        task = self.get(user, task_id)
        self.repo.delete(task)
        self.db.commit()

    @staticmethod
    def _apply_status(task: Task, status: TaskStatus) -> None:
        """status の変更に合わせて completed_at を自動で整合させる。"""
        if status is TaskStatus.DONE:
            if task.status is not TaskStatus.DONE:
                task.completed_at = datetime.now(UTC)
        else:
            task.completed_at = None
        task.status = status
