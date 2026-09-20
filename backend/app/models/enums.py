from enum import StrEnum


class TaskStatus(StrEnum):
    """タスクの進行状態。完了から未完了への戻しも想定する。"""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    """タスクの優先度。自動スケジューリングの並び順にも利用する。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
