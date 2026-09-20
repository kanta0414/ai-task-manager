from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """LLM に渡す1発言。system は別枠で渡すため role は user / assistant のみ。"""

    role: Role
    content: str


@dataclass(frozen=True)
class ChatResult:
    """LLM からの応答。Phase 6 で tool_calls を追加する。"""

    content: str
    provider: str
    model: str


class LLMProvider(ABC):
    """LLM プロバイダの共通インターフェース。

    アプリケーションはこの抽象だけに依存し、Claude / Ollama を差し替えられる。
    """

    name: str
    model: str

    @abstractmethod
    def chat(self, messages: list[ChatMessage], system: str) -> ChatResult:
        """会話履歴とシステムプロンプトから応答を生成する。"""

    @abstractmethod
    def is_available(self) -> bool:
        """接続できる状態かを返す（UI での案内に使う）。"""
