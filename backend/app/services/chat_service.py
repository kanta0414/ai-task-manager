import json
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMProvider, ToolCall
from app.models.user import User
from app.schemas.chat import ChatMessageIn
from app.services.tool_registry import PendingAction, ToolRegistry

WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]
# 送信するトークン量を抑えるため、直近のやり取りだけを渡す
MAX_HISTORY_MESSAGES = 20
# ツール呼び出しの往復が無限に続かないようにする
MAX_TOOL_ITERATIONS = 5


@dataclass
class ChatOutcome:
    reply: str
    provider: str
    model: str
    #: 実行したツール名（UI での説明用）
    executed_tools: list[str] = field(default_factory=list)
    #: データを変更したか（UI の再取得が必要か）
    mutated: bool = False
    #: ユーザーの承認待ち操作
    pending: PendingAction | None = None


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

# 操作のルール
- タスクや予定の操作は必ず提供されたツールを使う。
  ツールを使わずに「登録しました」などと答えてはいけない。
- 「明日」「今週」などの相対的な表現は、上の現在日時を基準に解釈する。
- 変更・削除の対象IDが分からないときは、先に検索ツールで対象を特定する。
  候補が複数あって一つに絞れない場合は、実行せずユーザーに確認する。
- ツールが承認待ち（confirmation_required）を返したら、勝手に再実行せず、
  ユーザーに確認を求めていることを伝える。
- ツールの実行後は、何をしたかを1〜2文で簡潔に報告する。

# 応答のルール
- 日本語で、簡潔に答える。
- 一覧を答えるときは箇条書きにする。
"""


class ChatService:
    """LLM との会話と、ツール実行のループを担当する。

    プロバイダの違い（Claude / Ollama）はここから見えない。
    """

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def reply(
        self,
        user: User,
        message: str,
        history: list[ChatMessageIn],
        registry: ToolRegistry,
    ) -> ChatOutcome:
        system = build_system_prompt(user)
        tools = registry.specs()

        recent = history[-MAX_HISTORY_MESSAGES:]
        messages: list[ChatMessage] = [
            ChatMessage(role=m.role, content=m.content) for m in recent
        ]
        messages.append(ChatMessage(role="user", content=message))

        outcome = ChatOutcome(reply="", provider=self.provider.name, model=self.provider.model)

        for _ in range(MAX_TOOL_ITERATIONS):
            result = self.provider.chat(messages, system=system, tools=tools)
            outcome.reply = result.content

            if not result.tool_calls:
                return outcome

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                )
            )

            for call in result.tool_calls:
                tool_outcome = registry.execute(call)
                outcome.executed_tools.append(call.name)
                outcome.mutated = outcome.mutated or tool_outcome.mutated

                if tool_outcome.pending is not None:
                    # 承認が必要な操作。ここで打ち切り、ユーザーの判断を待つ
                    outcome.pending = tool_outcome.pending
                    outcome.reply = result.content or tool_outcome.pending.description
                    return outcome

                messages.append(_tool_message(call, tool_outcome.content, tool_outcome.is_error))

        outcome.reply = (
            "操作を完了できませんでした。手順が多すぎるようなので、"
            "もう少し小さく分けて指示してください。"
        )
        return outcome

    def execute_confirmed(
        self, action: PendingAction, registry: ToolRegistry
    ) -> ChatOutcome:
        """ユーザーが承認した操作を実行する。

        LLM を再度呼ばずに確定的な文言を返す（余計な費用と待ち時間を避けるため）。
        引数は registry 側で再検証されるので、クライアントから返ってきた値を
        そのまま信用するわけではない。
        """
        call = ToolCall(id="confirmed", name=action.tool, arguments=action.arguments)
        tool_outcome = registry.execute(call, confirmed=True)

        if tool_outcome.is_error:
            detail = ""
            if isinstance(tool_outcome.content, dict):
                detail = str(tool_outcome.content.get("error", ""))
            reply = f"実行できませんでした。{detail}"
        else:
            reply = action.done_message

        return ChatOutcome(
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
