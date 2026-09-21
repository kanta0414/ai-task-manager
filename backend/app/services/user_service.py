from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def list_users(db: Session) -> list[User]:
    """全ユーザー。定期実行から使う。"""
    return list(db.execute(select(User).order_by(User.id)).scalars().all())
