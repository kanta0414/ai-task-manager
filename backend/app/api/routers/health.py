from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    """アプリケーションの死活確認。"""
    return {"status": "ok"}


@router.get("/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """DB 接続確認。Phase 0 の完了条件。"""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
