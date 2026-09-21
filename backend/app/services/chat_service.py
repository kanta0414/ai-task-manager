import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMProvider, ToolCall
from app.models.user import User
from app.services.conversation_service import ConversationService
from app.services.tool_registry import PendingAction, ToolRegistry

logger = logging.getLogger(__name__)

WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]
# ツール呼び出しの往復が無限に続かないようにする
MAX_TOOL_ITERATIONS = 5


@dataclass
class ChatOutcome:
    conversation_id: int
    reply: str
    provider: str
    model: str
    #: 実行したツール名（UI での説明用）
    executed_tools: list[str] = field(default_factory=list)
    #: データを変更したか（UI の再取得が必要か）
    mutated: bool = False
    #: ユーザーの承認待ち操作
    pending: PendingAction | None = None


def now_in(user: User) -> datetime:
    return datetime.now(ZoneInfo(user.timezone or get_settings().timezone))


def build_current_time_note(user: User) -> str:
    """利用者の発言の先頭に付ける現在日時。

    現在日時をシステムプロンプト側に置くと、分が変わるたびに
    「システムプロンプト＋Tool定義」が別物になり、LLM 側のプロンプトキャッシュが
    毎回捨てられる（ローカルLLMでは応答時間に直結する）。
    固定部分と可変部分を分けるため、可変な現在日時はこちらに置く。
    """
    now = now_in(user)
    return f"[現在日時: {now:%Y-%m-%d} ({WEEKDAYS_JA[now.weekday()]}) {now:%H:%M}]"


def build_system_prompt(user: User) -> str:
    """システムプロンプト（リクエストごとに変化しない固定部分）。"""
    tz = ZoneInfo(user.timezone or get_settings().timezone)

    return f"""あなたは「AI Task Manager」のアシスタントです。
ユーザーのタスクと予定の管理を手伝います。

# 前提
- タイムゾーン: {tz.key}。日時は 'YYYY-MM-DDTHH:MM' 形式で指定する。
- ユーザー名: {user.name}
- 現在日時は利用者の発言の先頭に [現在日時: ...] として与えられる。

# 操作のルール
- タスクや予定の操作は必ず提供されたツールを使う。
  ツールを使わずに「登録しました」などと答えてはいけない。
- 「明日」「今週」などの相対的な表現は、与えられた現在日時を基準に解釈する。
- 変更・削除の対象IDが分からないときは、先に検索ツールで対象を特定する。
  候補が複数あって一つに絞れない場合は、実行せずユーザーに確認する。
- ツールが承認待ち（confirmation_required）を返したら、勝手に再実行せず、
  ユーザーに確認を求めていることを伝える。
- ツールの実行後は、何をしたかを1〜2文で簡潔に報告する。

# 手順の例
- 「今日のタスクを教えて」
  → search_tasks を実行する（due_from に今日の0:00、due_to に今日の23:59）。
    結果を見てから答える。憶測で一覧を作らない。
- 「未完了のタスクは？」
  → search_tasks を statuses=["todo","in_progress"] で実行する。
- 「ESのタスクを削除して」
  → まず search_tasks を keyword="ES" で実行して id を確認し、
    その id で delete_task を呼ぶ。id を推測してはいけない。
- 「明日の企業研究を18時からにして」
  → search_events で対象の id を確認してから update_event を呼ぶ。

# 応答のルール
- 日本語で、簡潔に答える。
- 一覧を答えるときは箇条書きにする。
- ツールを実行していないのに「追加しました」「削除しました」と報告してはいけない。
"""


class ChatService:
    """LLM との会話と、ツール実行のループを担当する。

    プロバイダの違い（Claude / Ollama）はここから見えない。
    """

    def __init__(
        self, provider: LLMProvider, conversations: ConversationService
    ) -> None:
        self.provider = provider
        self.conversations = conversations

    def reply(
        self,
        user: User,
        message: str,
        conversation_id: int | None,
        registry: ToolRegistry,
    ) -> ChatOutcome:
        conversation = self.conversations.get_or_create(user, conversation_id)
        system = build_system_prompt(user)
        tools = registry.specs()

        # 履歴はDBから読む。「やっぱり19時からにして」のような指示で
        # 直前の対象を引き継げるようにするため。
        messages = self.conversations.history_for_llm(conversation)
        messages.append(
            ChatMessage(
                role="user",
                content=f"{build_current_time_note(user)}\n{message}",
            )
        )

        outcome = ChatOutcome(
            conversation_id=conversation.id,
            reply="",
            provider=self.provider.name,
            model=self.provider.model,
        )

        for _ in range(MAX_TOOL_ITERATIONS):
            result = self.provider.chat(messages, system=system, tools=tools)
            outcome.reply = result.content

            if not result.tool_calls:
                self.conversations.record_exchange(conversation, message, outcome.reply)
                return outcome

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                )
            )

            for call in result.tool_calls:
                # LLM が何をどう呼んだかを追えるようにする（引数の誤りの調査用）
                logger.info(
                    "tool call: %s %s",
                    call.name,
                    json.dumps(call.arguments, ensure_ascii=False),
                )
                tool_outcome = registry.execute(call)
                outcome.executed_tools.append(call.name)
                outcome.mutated = outcome.mutated or tool_outcome.mutated

                if tool_outcome.pending is not None:
                    # 承認が必要な操作。ここで打ち切り、ユーザーの判断を待つ
                    outcome.pending = tool_outcome.pending
                    outcome.reply = result.content or tool_outcome.pending.description
                    self.conversations.record_exchange(
                        conversation, message, outcome.reply
                    )
                    return outcome

                messages.append(_tool_message(call, tool_outcome.content, tool_outcome.is_error))

        outcome.reply = (
            "操作を完了できませんでした。手順が多すぎるようなので、"
            "もう少し小さく分けて指示してください。"
        )
        self.conversations.record_exchange(conversation, message, outcome.reply)
        return outcome

    def execute_confirmed(
        self,
        user: User,
        conversation_id: int,
        action: PendingAction,
        registry: ToolRegistry,
    ) -> ChatOutcome:
        """ユーザーが承認した操作を実行する。

        LLM を再度呼ばずに確定的な文言を返す（余計な費用と待ち時間を避けるため）。
        引数は registry 側で再検証されるので、クライアントから返ってきた値を
        そのまま信用するわけではない。
        """
        conversation = self.conversations.get(user, conversation_id)
        call = ToolCall(id="confirmed", name=action.tool, arguments=action.arguments)
        tool_outcome = registry.execute(call, confirmed=True)

        if tool_outcome.is_error:
            detail = ""
            if isinstance(tool_outcome.content, dict):
                detail = str(tool_outcome.content.get("error", ""))
            reply = f"実行できませんでした。{detail}"
        else:
            reply = action.done_message

        self.conversations.record_assistant_message(conversation, reply)

        return ChatOutcome(
            conversation_id=conversation.id,
            reply=reply,
            provider=self.provider.name,
            model=self.provider.model,
            executed_tools=[action.tool],
            mutated=tool_outcome.mutated,
        )


def _tool_message(call: ToolCall, content: object, is_error: bool) -> ChatMessage:
    return ChatMessage(
        role="tool",
        content=json.dumps(content, ensure_ascii=False, default=str),
        tool_call_id=call.id,
        tool_name=call.name,
        is_error=is_error,
    )
