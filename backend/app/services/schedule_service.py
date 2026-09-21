from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventSearchParams

#: 一度に走査できる期間の上限（取得件数と応答サイズを抑えるため）
MAX_PERIOD_DAYS = 31


@dataclass(frozen=True)
class FreeSlot:
    start_at: datetime
    end_at: datetime

    @property
    def minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


@dataclass(frozen=True)
class ScheduleConstraints:
    """予定を入れてよい時間帯のルール。

    **LLM に決めさせず Backend が持つ**（開発手順 15）。
    「23時〜7時は入れない」「土日は入れない」といった制約をここで表現する。
    """

    day_start_hour: int = 9
    day_end_hour: int = 22
    exclude_weekends: bool = False

    def describe(self) -> str:
        rule = f"{self.day_start_hour}:00〜{self.day_end_hour}:00 の範囲で探索"
        if self.exclude_weekends:
            rule += "（土日を除く）"
        return rule


class ScheduleService:
    """カレンダーの空き時間を計算する。

    LLM は「いつ空いているか」を推測せず、このサービスの結果を使う。
    """

    def __init__(self, db: Session) -> None:
        self.events = EventRepository(db)

    def find_free_time(
        self,
        user: User,
        *,
        period_start: datetime,
        period_end: datetime,
        minutes_needed: int,
        constraints: ScheduleConstraints | None = None,
    ) -> list[FreeSlot]:
        if period_end <= period_start:
            raise BusinessRuleError("終了日時は開始日時より後にしてください")
        if (period_end - period_start).days > MAX_PERIOD_DAYS:
            raise BusinessRuleError(
                f"一度に探せるのは{MAX_PERIOD_DAYS}日までです。期間を分けてください"
            )

        rules = constraints or default_constraints()
        tz = ZoneInfo(user.timezone or get_settings().timezone)

        busy = _merge(
            [
                (event.start_at, event.end_at)
                for event in self.events.search(
                    user.id,
                    EventSearchParams(from_=period_start, to=period_end, limit=1000),
                )
            ]
        )

        slots: list[FreeSlot] = []
        for day in _days_between(period_start, period_end, tz):
            if rules.exclude_weekends and day.weekday() >= 5:
                continue

            midnight = datetime.combine(day, time(0), tzinfo=tz)
            window_start = max(
                midnight + timedelta(hours=rules.day_start_hour), period_start
            )
            window_end = min(
                midnight + timedelta(hours=rules.day_end_hour), period_end
            )
            if window_end <= window_start:
                continue

            slots.extend(
                FreeSlot(start, end)
                for start, end in _gaps(window_start, window_end, busy)
                if (end - start).total_seconds() >= minutes_needed * 60
            )

        return slots


def default_constraints() -> ScheduleConstraints:
    settings = get_settings()
    return ScheduleConstraints(
        day_start_hour=settings.schedule_day_start_hour,
        day_end_hour=settings.schedule_day_end_hour,
    )


def _days_between(start: datetime, end: datetime, tz: ZoneInfo) -> list[date]:
    """期間に含まれる日付を、利用者のタイムゾーンで数える。"""
    first = start.astimezone(tz).date()
    last = end.astimezone(tz).date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """重なり合う予定を1つにまとめる（空き時間の計算を単純にするため）。"""
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            last_start, last_end = merged[-1]
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _gaps(
    window_start: datetime,
    window_end: datetime,
    busy: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """稼働時間帯から予定を差し引いた残りを返す。"""
    gaps: list[tuple[datetime, datetime]] = []
    cursor = window_start

    for start, end in busy:
        if end <= cursor:
            continue
        if start >= window_end:
            break
        if start > cursor:
            gaps.append((cursor, min(start, window_end)))
        cursor = max(cursor, end)
        if cursor >= window_end:
            return gaps

    if cursor < window_end:
        gaps.append((cursor, window_end))
    return gaps
