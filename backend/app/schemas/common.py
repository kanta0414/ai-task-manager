from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import AfterValidator

from app.core.config import get_settings


def _ensure_aware(value: datetime) -> datetime:
    """naive な日時にアプリのタイムゾーンを付与する。

    naive のまま timestamptz へ渡すと PostgreSQL のセッションタイムゾーンに
    依存して解釈がぶれるため、入口で必ず aware に正規化する。
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo(get_settings().timezone))
    return value


AwareDatetime = Annotated[datetime, AfterValidator(_ensure_aware)]
