from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health
from app.core.config import get_settings

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


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "AI Task Manager API", "docs": "/docs"}
