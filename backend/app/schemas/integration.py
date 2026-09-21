from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    """外部カレンダーの連携状況。"""

    #: サーバー側に認証情報が設定されているか（未設定なら連携ボタンを出さない）
    google_available: bool
    google_connected: bool
    google_account_email: str | None = None


class AuthorizeUrl(BaseModel):
    url: str
