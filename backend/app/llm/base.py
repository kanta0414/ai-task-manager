from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolSpec:
    """LLM に渡す Tool の定義（プロバイダ非依存）。

    input_schema は $ref を含まない素の JSON Schema。
    Claude は input_schema、Ollama は function.parameters として受け取る。
    """

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """LLM が要求した Tool 呼び出し。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatMessage:
    """会話の1メッセージ。

    role="assistant" のとき tool_calls を持つことがあり、
    role="tool" は その呼び出しに対する実行結果を表す。
    """

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    tool_call_id: str | None = None
    tool_name: str | None = None
    is_error: bool = False


@dataclass(frozen=True)
class ChatResult:
    """LLM からの応答。tool_calls があれば実行して会話を続ける。"""

    content: str
    provider: str
    model: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


class LLMProvider(ABC):
    """LLM プロバイダの共通インターフェース。

    アプリケーションはこの抽象だけに依存し、Claude / Ollama を差し替えられる。
    Tool の形式変換は各プロバイダの内部に閉じ込める。
    """

    name: str
    model: str

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolSpec] | None = None,
    ) -> ChatResult:
        """会話履歴とシステムプロンプトから応答を生成する。"""

    @abstractmethod
    def is_available(self) -> bool:
        """接続できる状態かを返す（UI での案内に使う）。"""
