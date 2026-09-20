from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.llm.base import ChatMessage, ChatResult, LLMProvider
from app.models.user import User
from app.schemas.chat import ChatMessageIn

WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]
# 送信するトークン量を抑えるため、直近のやり取りだけを渡す
MAX_HISTORY_MESSAGES = 20


def build_system_prompt(user: User) -> str:
    """システムプロンプト。

    「明日の14時」のような相対表現を LLM が正しく解釈できるよう、
    現在日時とタイムゾーンを必ず渡す。ここが曖昧だと日時が全てずれる。
    """
    tz = ZoneInfo(user.timezone or get_settings().timezone)
    now = datetime.now(tz)
    weekday = WEEKDAYS_JA[now.weekday()]

    return f"""あなたは「AI Task Manager」のアシスタントです。
ユーザーのタスクと予定の管理を手伝います。

# 現在の状況
- 現在日時: {now:%Y-%m-%d} ({weekday}) {now:%H:%M}
- タイムゾーン: {tz.key}
- ユーザー名: {user.name}

# 応答のルール
- 日本語で、簡潔に答える。
- 「明日」「今週」などの相対的な表現は、上の現在日時を基準に解釈する。
- まだタスクや予定を操作する機能は接続されていない。操作を求められたら、
  今は画面から操作してほしいと伝える（次の開発段階で対応予定であることも添える）。
"""


class ChatService:
    """LLM との会話を担当する。

    プロバイダの違い（Claude / Ollama）はここから見えない。
    """

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def reply(
        self, user: User, message: str, history: list[ChatMessageIn]
    ) -> ChatResult:
        recent = history[-MAX_HISTORY_MESSAGES:]
        messages = [ChatMessage(role=m.role, content=m.content) for m in recent]
        messages.append(ChatMessage(role="user", content=message))

        return self.provider.chat(messages, system=build_system_prompt(user))
