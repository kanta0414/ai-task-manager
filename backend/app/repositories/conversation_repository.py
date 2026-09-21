from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message
from app.models.enums import MessageRole


class ConversationRepository:
    """会話とメッセージの永続化のみを担当する。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: int) -> Conversation:
        conversation = Conversation(user_id=user_id)
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def get(self, conversation_id: int, user_id: int) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: int, limit: int = 30) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def add_message(
        self, conversation: Conversation, role: MessageRole, content: str
    ) -> Message:
        message = Message(
            conversation_id=conversation.id, role=role, content=content
        )
        self.db.add(message)
        self.db.flush()
        return message

    def recent_messages(
        self, conversation_id: int, user_id: int, limit: int
    ) -> list[Message]:
        """直近 limit 件を古い順で返す。

        呼び出し側で所有者を確認済みでも、ここでも会話の持ち主を条件に入れる
        （新しい呼び出しが増えたときに他人の発言が漏れないようにするため）。
        """
        stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.conversation_id == conversation_id,
                Conversation.user_id == user_id,
            )
            .order_by(Message.id.desc())
            .limit(limit)
        )
        return list(reversed(self.db.execute(stmt).scalars().all()))

    def delete(self, conversation: Conversation) -> None:
        self.db.delete(conversation)
        self.db.flush()
