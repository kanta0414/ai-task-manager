from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """会話履歴はサーバー側（conversations / messages）で管理する。

    conversation_id を省略すると新しい会話を開始する。
    """

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = Field(default=None, gt=0)


class PendingActionOut(BaseModel):
    """ユーザーの承認を待っている操作。UI に [実行][キャンセル] を出す。"""

    tool: str
    arguments: dict[str, Any]
    description: str


class ChatResponse(BaseModel):
    conversation_id: int
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

    conversation_id: int = Field(gt=0)
    tool: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any]
    description: str = Field(min_length=1, max_length=200)


class ChatStatus(BaseModel):
    """UI に「なぜAIが使えないか」を表示するための情報。"""

    provider: str
    model: str
    available: bool
    hint: str | None = None
