from fastapi import APIRouter

from app.api.deps import ChatServiceDep, CurrentUser, ToolRegistryDep
from app.schemas.chat import (
    ChatConfirmRequest,
    ChatRequest,
    ChatResponse,
    ChatStatus,
    PendingActionOut,
)
from app.services.chat_service import ChatOutcome
from app.services.tool_registry import PendingAction

router = APIRouter(prefix="/chat", tags=["chat"])


def _to_response(outcome: ChatOutcome) -> ChatResponse:
    return ChatResponse(
        conversation_id=outcome.conversation_id,
        reply=outcome.reply,
        provider=outcome.provider,
        model=outcome.model,
        executed_tools=outcome.executed_tools,
        mutated=outcome.mutated,
        pending_action=(
            PendingActionOut(
                tool=outcome.pending.tool,
                arguments=outcome.pending.arguments,
                description=outcome.pending.description,
            )
            if outcome.pending
            else None
        ),
    )


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user: CurrentUser,
    service: ChatServiceDep,
    registry: ToolRegistryDep,
) -> ChatResponse:
    return _to_response(
        service.reply(user, payload.message, payload.conversation_id, registry)
    )


@router.post("/confirm", response_model=ChatResponse)
def confirm(
    payload: ChatConfirmRequest,
    user: CurrentUser,
    service: ChatServiceDep,
    registry: ToolRegistryDep,
) -> ChatResponse:
    """ユーザーが承認した操作を実行する（削除など）。"""
    action = PendingAction(
        tool=payload.tool,
        arguments=payload.arguments,
        description=payload.description,
        done_message=payload.description.replace("します。", "しました。"),
    )
    return _to_response(
        service.execute_confirmed(
            user, payload.conversation_id, action, registry
        )
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
