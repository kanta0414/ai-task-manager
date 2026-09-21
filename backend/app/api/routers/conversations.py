from fastapi import APIRouter, status

from app.api.deps import ConversationServiceDep, CurrentUser
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationDetail, ConversationRead

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    user: CurrentUser, service: ConversationServiceDep
) -> list[Conversation]:
    """会話の一覧を新しい順に返す。"""
    return service.list_for_user(user)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int, user: CurrentUser, service: ConversationServiceDep
) -> Conversation:
    """会話を発言込みで取得する。"""
    return service.get(user, conversation_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int, user: CurrentUser, service: ConversationServiceDep
) -> None:
    """会話を発言ごと削除する。"""
    service.delete(user, conversation_id)
