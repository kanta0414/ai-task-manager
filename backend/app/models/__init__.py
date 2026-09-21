"""SQLAlchemy モデル。

Alembic の autogenerate はここで import されたモデルを対象にするため、
新しいモデルを追加したら必ずこのファイルにも追記する。
"""

from app.models.calendar_event import CalendarEvent
from app.models.conversation import Conversation, Message
from app.models.enums import (
    MessageRole,
    NotificationKind,
    TaskPriority,
    TaskStatus,
)
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User

__all__ = [
    "CalendarEvent",
    "Conversation",
    "Message",
    "MessageRole",
    "Notification",
    "NotificationKind",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "User",
]
