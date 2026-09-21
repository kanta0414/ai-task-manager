import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import (
    auth,
    chat,
    conversations,
    events,
    health,
    integrations,
    notifications,
    schedule,
    tasks,
)
from app.core.config import get_settings
from app.core.exceptions import (
    BusinessRuleError,
    ConflictError,
    LLMError,
    LLMUnavailableError,
    NotFoundError,
    UnauthorizedError,
)

settings = get_settings()

# LLM がどのツールをどんな引数で呼んだかを追えるようにする
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(
    title="AI Task Manager API",
    version="0.1.0",
    description=(
        "通常UIとLLM Tool Calling が同一の Service Layer を利用する"
        "タスク・スケジュール管理API"
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # セッション Cookie を送受信するため許可する。
    # allow_origins は列挙した値のみ（ワイルドカード不可）
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

#: リクエスト本文の上限。Pydantic の検証は本文を読み込んだ後に効くため、
#: その手前で大きすぎるリクエストを落とす
MAX_REQUEST_BYTES = 1_000_000


@app.middleware("http")
async def limit_request_size(request: Request, call_next):  # noqa: ANN001, ANN201
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413, content={"detail": "リクエストが大きすぎます。"}
                )
        except ValueError:
            return JSONResponse(
                status_code=400, content={"detail": "Content-Length が不正です。"}
            )
    return await call_next(request)


app.include_router(auth.router)
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(events.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(schedule.router)
app.include_router(integrations.router)
app.include_router(notifications.router)


# Service Layer のドメイン例外を HTTP へ変換する。
# Service 自体は HTTP を知らないため、LLM Tool からも同じ例外を扱える。
@app.exception_handler(UnauthorizedError)
def handle_unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": exc.message})


@app.exception_handler(ConflictError)
def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(BusinessRuleError)
def handle_business_rule(request: Request, exc: BusinessRuleError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.exception_handler(LLMUnavailableError)
def handle_llm_unavailable(request: Request, exc: LLMUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.exception_handler(LLMError)
def handle_llm_error(request: Request, exc: LLMError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": exc.message})


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AI Task Manager API", "docs": "/docs"}
