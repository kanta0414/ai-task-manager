from typing import Any

import anthropic

from app.core.exceptions import LLMError, LLMUnavailableError
from app.llm.base import ChatMessage, ChatResult, LLMProvider, ToolCall, ToolSpec

MAX_TOKENS = 8000


class ClaudeProvider(LLMProvider):
    """Claude API を利用するプロバイダ。

    **注意: 呼び出すと従量課金が発生する。**
    LLM_PROVIDER=claude に切り替えたときだけ使われる（既定は ollama）。
    """

    name = "claude"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._api_key = api_key
        # APIキーが無い状態でクライアントを作ると生成時に失敗するため遅延生成する
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if not self._api_key:
            raise LLMUnavailableError(
                "ANTHROPIC_API_KEY が設定されていません。backend/.env に設定してください。"
            )
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def chat(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolSpec] | None = None,
    ) -> ChatResult:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": to_claude_messages(messages),
        }
        if tools:
            request["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]

        try:
            response = self.client.messages.create(**request)
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailableError(
                "Claude API の認証に失敗しました（APIキーを確認してください）。"
            ) from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"モデル '{self.model}' が利用できません。") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError(
                "Claude API のレート制限に達しました。時間をおいて再試行してください。"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Claude API がエラーを返しました（{exc.status_code}）。") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailableError("Claude API に接続できません。") from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        calls = tuple(
            ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            for block in response.content
            if block.type == "tool_use"
        )
        return ChatResult(
            content=text, provider=self.name, model=self.model, tool_calls=calls
        )

    def is_available(self) -> bool:
        """APIキーの有無だけを見る（確認のためにAPIを呼ぶと課金されるため）。"""
        return bool(self._api_key)


def to_claude_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """共通表現を Claude の messages 形式へ変換する。

    連続する tool 実行結果は **1つの user メッセージにまとめる**。
    分割して送ると並列 Tool 呼び出しが抑制されてしまうため。
    """
    converted: list[dict[str, Any]] = []
    pending_results: list[dict[str, Any]] = []

    def flush_results() -> None:
        if pending_results:
            converted.append({"role": "user", "content": list(pending_results)})
            pending_results.clear()

    for message in messages:
        if message.role == "tool":
            pending_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                    "is_error": message.is_error,
                }
            )
            continue

        flush_results()

        if message.role == "assistant" and message.tool_calls:
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            blocks.extend(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
            converted.append({"role": "assistant", "content": blocks})
        else:
            converted.append({"role": message.role, "content": message.content})

    flush_results()
    return converted
