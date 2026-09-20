from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import events, health, tasks
from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, NotFoundError

settings = get_settings()

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


# Service Layer のドメイン例外を HTTP へ変換する。
# Service 自体は HTTP を知らないため、LLM Tool からも同じ例外を扱える。
@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(BusinessRuleError)
def handle_business_rule(request: Request, exc: BusinessRuleError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AI Task Manager API", "docs": "/docs"}
