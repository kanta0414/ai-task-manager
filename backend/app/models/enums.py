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


class MessageRole(StrEnum):
    """会話メッセージの発言者。"""

    USER = "user"
    ASSISTANT = "assistant"


class NotificationKind(StrEnum):
    """通知の種類。"""

    #: 予定の開始が近い
    REMINDER = "reminder"
    #: 朝の予定・タスクのまとめ
    DAILY_DIGEST = "daily_digest"
    #: 終わらなかった作業の組み直し提案
    UNFINISHED = "unfinished"
