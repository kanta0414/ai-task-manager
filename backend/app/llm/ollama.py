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

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        disable_thinking: bool = True,
        num_ctx: int = 6144,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        # 既定の 4096 だと Tool 定義 + 履歴で溢れ、古い部分が黙って切り捨てられる
        self.num_ctx = num_ctx
        # qwen3 などの thinking 対応モデルは、思考トークンの分だけ CPU では
        # 目に見えて遅くなる。Tool Calling が目的なので既定で切る。
        self.disable_thinking = disable_thinking

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
            "options": {
                # Tool の選択は揺らがせたくないので貪欲デコードにする
                "temperature": 0,
                "num_ctx": self.num_ctx,
            },
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

        if self.disable_thinking:
            payload["think"] = False

        response = self._post(payload)

        # thinking 非対応のモデルは "think" を拒否するので、その場合は外して再試行
        if response.status_code == 400 and "think" in response.text.lower():
            payload.pop("think", None)
            response = self._post(payload)

        if response.status_code == 404:
            raise LLMUnavailableError(
                f"モデル '{self.model}' が見つかりません。"
                f"`ollama pull {self.model}` で取得してください。"
            )
        if response.status_code >= 400:
            raise LLMError(f"Ollama がエラーを返しました: {response.text[:200]}")

        message = response.json().get("message", {})
        content = message.get("content", "")
        calls = parse_tool_calls(message.get("tool_calls") or [])

        # 小型モデルは Tool 呼び出しを本文のテキストとして出すことがある。
        # 引数は結局 Backend で検証するので、拾えるものは拾って実行する。
        if not calls:
            recovered = recover_tool_call_from_text(content)
            if recovered is not None:
                calls = (recovered,)
                content = ""

        return ChatResult(
            content=content,
            provider=self.name,
            model=self.model,
            tool_calls=calls,
        )

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        try:
            return httpx.post(
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


def recover_tool_call_from_text(content: str) -> ToolCall | None:
    """本文に紛れ込んだ Tool 呼び出しの JSON を拾う。

    小型モデルでよくある失敗（tool_calls ではなく本文に
    {"name": "...", "arguments": {...}} を書く）への対処。
    形が違えば None を返し、通常の発言として扱う。
    """
    text = content.strip()
    if not text:
        return None

    # ```json ... ``` で囲まれている場合を剥がす
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    name = parsed.get("name")
    arguments = parsed.get("arguments", {})
    if not isinstance(name, str) or not name or not isinstance(arguments, dict):
        return None

    return ToolCall(id="recovered_0", name=name, arguments=arguments)
