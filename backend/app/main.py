import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import chat, conversations, events, health, schedule, tasks
from app.core.config import get_settings
from app.core.exceptions import (
    BusinessRuleError,
    LLMError,
    LLMUnavailableError,
    NotFoundError,
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(events.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(schedule.router)


# Service Layer のドメイン例外を HTTP へ変換する。
# Service 自体は HTTP を知らないため、LLM Tool からも同じ例外を扱える。
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
