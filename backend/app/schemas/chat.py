from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """会話履歴は Phase 9 でDBに保存する。それまではクライアントから受け取る。"""

    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessageIn] = Field(default_factory=list, max_length=40)


class PendingActionOut(BaseModel):
    """ユーザーの承認を待っている操作。UI に [実行][キャンセル] を出す。"""

    tool: str
    arguments: dict[str, Any]
    description: str


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    #: 実行したツール名
    executed_tools: list[str] = Field(default_factory=list)
    #: データが変わったか（UI 側でタスク・予定を再取得する）
    mutated: bool = False
    pending_action: PendingActionOut | None = None


class ChatConfirmRequest(BaseModel):
    """承認された操作の実行依頼。

    引数は Backend 側で再検証・権限確認されるため、そのまま信用はしない。
    """

    tool: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any]
    description: str = Field(min_length=1, max_length=200)


class ChatStatus(BaseModel):
    """UI に「なぜAIが使えないか」を表示するための情報。"""

    provider: str
    model: str
    available: bool
    hint: str | None = None
