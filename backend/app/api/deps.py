from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.llm.factory import get_llm_provider
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.tool_registry import ToolRegistry
from app.integrations.calendar_client import CalendarClient, GoogleCalendarClient
from app.services.event_service import EventService
from app.services.external_calendar_service import ExternalCalendarService
from app.services.notification_service import NotificationService
from app.services.schedule_service import ScheduleService
from app.services.task_service import TaskService

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    session: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> User:
    """現在のユーザーを返す唯一の入口。

    セッション Cookie の JWT からユーザーを特定する。
    全てのデータ操作がここを通るため、ここが返すユーザー以外のデータには触れない。
    """
    if session is None:
        raise UnauthorizedError("ログインしてください")

    user_id = decode_access_token(session)
    if user_id is None:
        raise UnauthorizedError("セッションの有効期限が切れています")

    user = db.get(User, user_id)
    if user is None:
        # ユーザーが削除された後もトークンは残りうる
        raise UnauthorizedError("ログインしてください")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_task_service(db: DbSession) -> TaskService:
    return TaskService(db)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


def get_event_service(db: DbSession) -> EventService:
    return EventService(db)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]


def get_conversation_service(db: DbSession) -> ConversationService:
    return ConversationService(db)


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


def get_chat_service(conversations: ConversationServiceDep) -> ChatService:
    return ChatService(get_llm_provider(), conversations)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_tool_registry(db: DbSession, user: CurrentUser) -> ToolRegistry:
    """LLM が実行できる操作。通常UIと同じ Service を経由する。"""
    return ToolRegistry(db, user)


ToolRegistryDep = Annotated[ToolRegistry, Depends(get_tool_registry)]


def get_calendar_client() -> CalendarClient | None:
    """Google の認証情報が設定されていなければ None（連携機能は無効）。"""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        return None
    return GoogleCalendarClient(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def get_external_calendar_service(db: DbSession) -> ExternalCalendarService:
    return ExternalCalendarService(db, get_calendar_client())


ExternalCalendarServiceDep = Annotated[
    ExternalCalendarService, Depends(get_external_calendar_service)
]


def get_schedule_service(
    db: DbSession, external: ExternalCalendarServiceDep
) -> ScheduleService:
    return ScheduleService(db, external)


ScheduleServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]


def get_notification_service(db: DbSession) -> NotificationService:
    return NotificationService(db)


NotificationServiceDep = Annotated[
    NotificationService, Depends(get_notification_service)
]


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
