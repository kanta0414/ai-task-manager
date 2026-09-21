from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models.calendar_event import CalendarEvent
from app.models.user import User
from app.services.schedule_service import ScheduleConstraints, ScheduleService

JST = ZoneInfo("Asia/Tokyo")


def at(text: str) -> datetime:
    """'2026-09-22 14:00' を JST の日時にする。"""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


@pytest.fixture
def service(db: Session) -> ScheduleService:
    return ScheduleService(db)


def add_event(db: Session, user: User, title: str, start: str, end: str) -> None:
    db.add(
        CalendarEvent(
            user_id=user.id, title=title, start_at=at(start), end_at=at(end)
        )
    )
    db.flush()


def find(service: ScheduleService, user: User, start: str, end: str, minutes: int, **kw):
    return service.find_free_time(
        user,
        period_start=at(start),
        period_end=at(end),
        minutes_needed=minutes,
        **kw,
    )


def as_text(slots) -> list[str]:
    return [
        f"{s.start_at.astimezone(JST):%m/%d %H:%M}-{s.end_at.astimezone(JST):%H:%M}"
        for s in slots
    ]


def test_empty_calendar_returns_the_whole_working_window(
    service: ScheduleService, user: User
) -> None:
    slots = find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 60)
    assert as_text(slots) == ["09/22 09:00-22:00"]


def test_event_splits_the_day(service: ScheduleService, user: User, db: Session) -> None:
    add_event(db, user, "会議", "2026-09-22 13:00", "2026-09-22 15:00")

    slots = find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 60)
    assert as_text(slots) == ["09/22 09:00-13:00", "09/22 15:00-22:00"]


def test_minutes_needed_filters_short_gaps(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_event(db, user, "午前", "2026-09-22 09:00", "2026-09-22 12:00")
    add_event(db, user, "午後", "2026-09-22 13:00", "2026-09-22 22:00")

    # 12:00-13:00 の1時間だけ空いている
    assert as_text(find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 60)) == [
        "09/22 12:00-13:00"
    ]
    assert find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 90) == []


def test_full_day_event_leaves_nothing(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_event(db, user, "終日", "2026-09-22 08:00", "2026-09-22 23:00")
    assert find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 30) == []


def test_events_outside_working_hours_are_ignored(
    service: ScheduleService, user: User, db: Session
) -> None:
    """深夜の予定は 9:00-22:00 の空きに影響しない。"""
    add_event(db, user, "夜更かし", "2026-09-22 23:00", "2026-09-23 01:00")

    assert as_text(find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 60)) == [
        "09/22 09:00-22:00"
    ]


def test_overlapping_events_are_merged(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_event(db, user, "A", "2026-09-22 13:00", "2026-09-22 15:00")
    add_event(db, user, "B", "2026-09-22 14:00", "2026-09-22 16:00")

    assert as_text(find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 60)) == [
        "09/22 09:00-13:00",
        "09/22 16:00-22:00",
    ]


def test_multiple_days(service: ScheduleService, user: User, db: Session) -> None:
    add_event(db, user, "初日の予定", "2026-09-22 09:00", "2026-09-22 22:00")

    slots = find(service, user, "2026-09-22 00:00", "2026-09-24 00:00", 60)
    assert as_text(slots) == ["09/23 09:00-22:00"]


def test_period_start_clips_the_first_day(
    service: ScheduleService, user: User
) -> None:
    """「今から」探す場合、開始時刻より前は候補に出さない。"""
    slots = find(service, user, "2026-09-22 15:30", "2026-09-23 00:00", 60)
    assert as_text(slots) == ["09/22 15:30-22:00"]


def test_exclude_weekends(service: ScheduleService, user: User) -> None:
    # 2026-09-26(土) と 27(日) を含む期間
    slots = find(
        service,
        user,
        "2026-09-25 00:00",
        "2026-09-28 00:00",
        60,
        constraints=ScheduleConstraints(exclude_weekends=True),
    )
    assert as_text(slots) == ["09/25 09:00-22:00"]


def test_custom_working_hours(service: ScheduleService, user: User) -> None:
    slots = find(
        service,
        user,
        "2026-09-22 00:00",
        "2026-09-23 00:00",
        60,
        constraints=ScheduleConstraints(day_start_hour=19, day_end_hour=23),
    )
    assert as_text(slots) == ["09/22 19:00-23:00"]


def test_other_users_events_do_not_block(
    service: ScheduleService, user: User, db: Session
) -> None:
    other = User(name="他人", email="other-sched@example.com")
    db.add(other)
    db.flush()
    db.add(
        CalendarEvent(
            user_id=other.id,
            title="他人の終日予定",
            start_at=at("2026-09-22 09:00"),
            end_at=at("2026-09-22 22:00"),
        )
    )
    db.flush()

    assert as_text(find(service, user, "2026-09-22 00:00", "2026-09-23 00:00", 60)) == [
        "09/22 09:00-22:00"
    ]


def test_rejects_inverted_period(service: ScheduleService, user: User) -> None:
    with pytest.raises(BusinessRuleError):
        find(service, user, "2026-09-23 00:00", "2026-09-22 00:00", 60)


def test_rejects_too_long_period(service: ScheduleService, user: User) -> None:
    with pytest.raises(BusinessRuleError, match="31日"):
        find(service, user, "2026-09-01 00:00", "2026-11-01 00:00", 60)
