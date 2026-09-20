from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User


def get_or_create_default_user(db: Session) -> User:
    """個人利用向けの既定ユーザーを返す（なければ作成する）。

    認証は Phase 16 で実装する。それまでは「現在のユーザー」をここ1箇所で
    決めておき、認証導入時は get_current_user の差し替えだけで済むようにする。
    """
    settings = get_settings()
    stmt = select(User).where(User.email == settings.default_user_email)
    user = db.execute(stmt).scalar_one_or_none()
    if user is None:
        user = User(
            name=settings.default_user_name,
            email=settings.default_user_email,
            timezone=settings.timezone,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
