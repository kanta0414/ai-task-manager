from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm.factory import get_llm_provider
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.tool_registry import ToolRegistry
from app.services.event_service import EventService
from app.services.task_service import TaskService
from app.services.user_service import get_or_create_default_user

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession) -> User:
    """現在のユーザーを返す唯一の入口。

    Phase 16 で認証を入れる際は、この関数だけを JWT 等の実装に差し替える。
    """
    return get_or_create_default_user(db)


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
