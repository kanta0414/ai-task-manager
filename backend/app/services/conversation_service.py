from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.llm.base import ChatMessage
from app.models.conversation import Conversation, Message
from app.models.enums import MessageRole
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository

#: LLM に渡す履歴の上限（トークン量を抑えるため）
MAX_HISTORY_MESSAGES = 20
#: 一覧表示用のタイトルの長さ
TITLE_LENGTH = 40


class ConversationService:
    """会話の保存と読み出し。

    これがある前に会話履歴はクライアントが持っていた。DB に移すことで
    リロードしても会話が続き、別の画面からも同じ会話を参照できる。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ConversationRepository(db)

    def get_or_create(self, user: User, conversation_id: int | None) -> Conversation:
        if conversation_id is None:
            conversation = self.repo.create(user.id)
            self.db.commit()
            self.db.refresh(conversation)
            return conversation

        conversation = self.repo.get(conversation_id, user.id)
        if conversation is None:
            raise NotFoundError("会話", conversation_id)
        return conversation

    def get(self, user: User, conversation_id: int) -> Conversation:
        conversation = self.repo.get(conversation_id, user.id)
        if conversation is None:
            raise NotFoundError("会話", conversation_id)
        return conversation

    def list_for_user(self, user: User) -> list[Conversation]:
        return self.repo.list_for_user(user.id)

    def delete(self, user: User, conversation_id: int) -> None:
        self.repo.delete(self.get(user, conversation_id))
        self.db.commit()

    def history_for_llm(self, conversation: Conversation) -> list[ChatMessage]:
        """LLM に渡す直近の会話。"""
        return [
            ChatMessage(role=message.role.value, content=message.content)
            for message in self.repo.recent_messages(
                conversation.id, MAX_HISTORY_MESSAGES
            )
        ]

    def record_exchange(
        self, conversation: Conversation, user_message: str, assistant_message: str
    ) -> None:
        """1往復を保存する。"""
        self.repo.add_message(conversation, MessageRole.USER, user_message)
        if assistant_message:
            self.repo.add_message(
                conversation, MessageRole.ASSISTANT, assistant_message
            )

        if conversation.title is None:
            conversation.title = _make_title(user_message)
        # 一覧を「最近使った順」に並べるため、メッセージ追加でも更新時刻を進める
        conversation.updated_at = datetime.now(timezone.utc)

        self.db.commit()

    def record_assistant_message(
        self, conversation: Conversation, content: str
    ) -> Message:
        """承認後の実行結果など、AI 側の発言だけを保存する。"""
        message = self.repo.add_message(conversation, MessageRole.ASSISTANT, content)
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return message


def _make_title(first_message: str) -> str:
    title = first_message.strip().splitlines()[0]
    if len(title) <= TITLE_LENGTH:
        return title
    return title[: TITLE_LENGTH - 1] + "…"
