from datetime import datetime

from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    """外部カレンダーの連携状況。"""

    #: サーバー側に認証情報が設定されているか（未設定なら連携ボタンを出さない）
    google_available: bool
    google_connected: bool
    google_account_email: str | None = None
    #: 更新トークンが失効し、つなぎ直しが必要な状態
    google_needs_reauth: bool = False


class AuthorizeUrl(BaseModel):
    url: str


class BusyIntervalRead(BaseModel):
    """外部カレンダーで埋まっている時間帯。予定の内容は取得していない。"""

    start_at: datetime
    end_at: datetime


class BusyIntervalsResponse(BaseModel):
    count: int
    intervals: list[BusyIntervalRead]
