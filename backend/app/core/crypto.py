"""保存するトークンの暗号化。

外部サービスの refresh token は、漏れると本人になりすませてしまう。
DBに平文で置かず、SECRET_KEY から導いた鍵で暗号化する。
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    secret = get_settings().secret_key
    if not secret:
        raise RuntimeError(
            "SECRET_KEY が設定されていません。backend/.env に設定してください。"
        )
    # Fernet は32バイトのURLセーフなbase64鍵を要求する
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str | None:
    """復号する。鍵が変わった等で復号できない場合は None。"""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return None
