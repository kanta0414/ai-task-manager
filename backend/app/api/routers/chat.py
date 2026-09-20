from fastapi import APIRouter

from app.api.deps import ChatServiceDep, CurrentUser
from app.schemas.chat import ChatRequest, ChatResponse, ChatStatus

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest, user: CurrentUser, service: ChatServiceDep
) -> ChatResponse:
    result = service.reply(user, payload.message, payload.history)
    return ChatResponse(
        reply=result.content, provider=result.provider, model=result.model
    )


@router.get("/status", response_model=ChatStatus)
def chat_status(service: ChatServiceDep) -> ChatStatus:
    """AI が使える状態かを返す。使えない理由を UI に表示するために使う。"""
    provider = service.provider
    available = provider.is_available()

    hint = None
    if not available and provider.name == "ollama":
        hint = (
            f"Ollama が起動していないか、モデル '{provider.model}' が未取得です。"
            f"`ollama serve` と `ollama pull {provider.model}` を実行してください。"
        )
    elif not available and provider.name == "claude":
        hint = "backend/.env の ANTHROPIC_API_KEY を設定してください。"

    return ChatStatus(
        provider=provider.name,
        model=provider.model,
        available=available,
        hint=hint,
    )
