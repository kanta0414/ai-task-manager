from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest


class AuthService:
    """ユーザー登録と認証。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, data: RegisterRequest) -> User:
        if self._find_by_email(data.email) is not None:
            raise ConflictError("このメールアドレスは既に登録されています")

        try:
            ZoneInfo(data.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise BusinessRuleError(
                f"タイムゾーン '{data.timezone}' は使用できません"
            ) from exc

        user = User(
            name=data.name,
            email=str(data.email).lower(),
            timezone=data.timezone,
            password_hash=hash_password(data.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> User | None:
        """メールとパスワードが一致すればユーザーを返す。

        「メールが無い」と「パスワードが違う」を呼び出し側から区別できないようにし、
        登録済みメールアドレスの推測を防ぐ。
        """
        user = self._find_by_email(email)
        if user is None:
            # 存在しない場合も同程度の時間をかけ、応答時間から推測されないようにする
            verify_password(password, hash_password("dummy"))
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def _find_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == str(email).lower())
        return self.db.execute(stmt).scalar_one_or_none()
