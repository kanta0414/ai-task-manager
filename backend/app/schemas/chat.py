from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """会話履歴は Phase 9 でDBに保存する。それまではクライアントから受け取る。"""

    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessageIn] = Field(default_factory=list, max_length=40)


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str


class ChatStatus(BaseModel):
    """UI に「なぜAIが使えないか」を表示するための情報。"""

    provider: str
    model: str
    available: bool
    hint: str | None = None
