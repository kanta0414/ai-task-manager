import json
from typing import Any

import httpx

from app.core.exceptions import LLMError, LLMUnavailableError
from app.llm.base import ChatMessage, ChatResult, LLMProvider, ToolCall, ToolSpec

# ローカルLLMは生成が遅いことがあるため長めに取る
REQUEST_TIMEOUT_SECONDS = 300.0


class OllamaProvider(LLMProvider):
    """ローカルの Ollama を利用するプロバイダ。

    API 料金がかからず、データを外部へ送らない構成（要件定義書 30）。
    Ollama は OpenAI 互換ではない独自の HTTP API を持つため httpx で直接呼ぶ。
    """

    name = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolSpec] | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                *to_ollama_messages(messages),
            ],
            "stream": False,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in tools
            ]

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.ConnectError as exc:
            raise LLMUnavailableError(
                "Ollama に接続できません。`ollama serve` が起動しているか確認してください。"
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError("Ollama の応答がタイムアウトしました。") from exc

        if response.status_code == 404:
            raise LLMUnavailableError(
                f"モデル '{self.model}' が見つかりません。"
                f"`ollama pull {self.model}` で取得してください。"
            )
        if response.status_code >= 400:
            raise LLMError(f"Ollama がエラーを返しました: {response.text[:200]}")

        message = response.json().get("message", {})
        return ChatResult(
            content=message.get("content", ""),
            provider=self.name,
            model=self.model,
            tool_calls=parse_tool_calls(message.get("tool_calls") or []),
        )

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
        except httpx.HTTPError:
            return False
        if response.status_code != 200:
            return False
        # モデル名は "llama3.2:3b" のようにタグ付き。タグ省略指定にも対応する
        installed = {m["name"] for m in response.json().get("models", [])}
        return self.model in installed or any(
            name.split(":")[0] == self.model.split(":")[0] for name in installed
        )


def to_ollama_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """共通表現を Ollama の messages 形式へ変換する。

    Ollama の tool 呼び出しには ID が無く、直前の assistant の呼び出しと
    順序で対応づけられる。
    """
    converted: list[dict[str, Any]] = []

    for message in messages:
        if message.role == "tool":
            converted.append(
                {
                    "role": "tool",
                    "content": message.content,
                    # バージョンによって参照するキーが異なるため両方入れる
                    "tool_name": message.tool_name,
                    "name": message.tool_name,
                }
            )
            continue

        entry: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.tool_calls:
            entry["tool_calls"] = [
                {"function": {"name": call.name, "arguments": call.arguments}}
                for call in message.tool_calls
            ]
        converted.append(entry)

    return converted


def parse_tool_calls(raw_calls: list[dict[str, Any]]) -> tuple[ToolCall, ...]:
    """Ollama の tool_calls を共通表現へ変換する。

    arguments は dict で返るが、文字列(JSON)で返す実装もあるため両方扱う。
    ID は無いので通し番号を振る。
    """
    calls: list[ToolCall] = []

    for index, raw in enumerate(raw_calls):
        function = raw.get("function", {})
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}

        calls.append(
            ToolCall(
                id=raw.get("id") or f"call_{index}",
                name=function.get("name", ""),
                arguments=arguments,
            )
        )

    return tuple(calls)
