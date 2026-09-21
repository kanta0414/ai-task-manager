"""パスワードのハッシュ化とアクセストークンの発行。"""

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"


def _prepare(password: str) -> bytes:
    """bcrypt に渡す前処理。

    bcrypt は72バイトを超える入力を黙って切り捨てる。日本語のパスワードは
    1文字3バイトになるため、24文字で上限に達してしまう。
    先に SHA-256 で固定長へ潰してから渡すことでこの制限を回避する
    （NUL バイトを避けるため base64 にする）。
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode())
    except ValueError:
        # ハッシュの形式が壊れている場合も「一致しない」として扱う
        return False


def _secret_key() -> str:
    key = get_settings().secret_key
    if not key:
        raise RuntimeError(
            "SECRET_KEY が設定されていません。backend/.env に設定してください。"
        )
    return key


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=get_settings().access_token_expire_minutes),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """トークンから user_id を取り出す。不正なら None。"""
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None
