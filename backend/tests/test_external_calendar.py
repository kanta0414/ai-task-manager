"""Google Calendar 連携（Phase 17）のテスト。

実際の Google は呼ばず、偽クライアントで検証する。
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_external_calendar_service
from app.core.crypto import decrypt, encrypt
from app.integrations.calendar_client import BusyInterval, OAuthTokens
from app.main import app
from app.models.calendar_event import CalendarEvent
from app.models.external_calendar import ExternalCalendarAccount
from app.models.user import User
from app.services.external_calendar_service import ExternalCalendarService
from app.services.schedule_service import ScheduleService

JST = ZoneInfo("Asia/Tokyo")


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


class FakeCalendarClient:
    """Google の代わり。呼ばれた内容を記録する。"""

    def __init__(self, busy: list[BusyInterval] | None = None) -> None:
        self.busy = busy or []
        self.refresh_calls = 0
        self.exchanged_code: str | None = None

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        return f"https://example.com/consent?state={state}&redirect_uri={redirect_uri}"

    def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokens:
        self.exchanged_code = code
        return OAuthTokens(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        self.refresh_calls += 1
        return OAuthTokens(
            access_token="access-2",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def fetch_account_email(self, access_token: str) -> str:
        return "me@gmail.com"

    def fetch_busy(self, access_token, start, end) -> list[BusyInterval]:
        return self.busy


@pytest.fixture
def client_stub() -> FakeCalendarClient:
    return FakeCalendarClient()


@pytest.fixture
def service(db: Session, client_stub: FakeCalendarClient) -> ExternalCalendarService:
    return ExternalCalendarService(db, client_stub)


# ------------------------------------------------------------------ 暗号化


def test_tokens_are_encrypted_at_rest(
    service: ExternalCalendarService, user: User, db: Session
) -> None:
    """refresh token は平文で保存しない。"""
    service.connect(user, code="auth-code")

    account = db.query(ExternalCalendarAccount).one()
    assert account.refresh_token_encrypted != "refresh-1"
    assert "refresh-1" not in account.refresh_token_encrypted
    assert decrypt(account.refresh_token_encrypted) == "refresh-1"


def test_decrypt_returns_none_for_broken_value() -> None:
    assert decrypt("これは暗号文ではない") is None
    assert decrypt(encrypt("ok")) == "ok"


# -------------------------------------------------------------- 接続手続き


def test_state_is_signed_and_identifies_the_user(
    service: ExternalCalendarService, user: User
) -> None:
    url = service.authorize_url(user)
    state = url.split("state=")[1].split("&")[0]

    assert service.user_id_from_state(state) == user.id


def test_tampered_state_is_rejected(service: ExternalCalendarService, user: User) -> None:
    url = service.authorize_url(user)
    state = url.split("state=")[1].split("&")[0]

    assert service.user_id_from_state(state[:-2] + "xx") is None
    assert service.user_id_from_state("でたらめ") is None


def test_state_from_another_purpose_is_rejected(
    service: ExternalCalendarService, user: User
) -> None:
    """別用途の署名トークン（セッションなど）を state に流用できない。"""
    from app.core.security import create_access_token

    assert service.user_id_from_state(create_access_token(user.id)) is None


def test_reconnect_updates_the_same_account(
    service: ExternalCalendarService, user: User, db: Session
) -> None:
    service.connect(user, code="one")
    service.connect(user, code="two")

    assert db.query(ExternalCalendarAccount).count() == 1


def test_disconnect_removes_the_stored_tokens(
    service: ExternalCalendarService, user: User, db: Session
) -> None:
    service.connect(user, code="auth-code")
    service.disconnect(user)

    assert db.query(ExternalCalendarAccount).count() == 0


# ------------------------------------------------------------ トークン更新


def test_expired_access_token_is_refreshed(
    service: ExternalCalendarService,
    client_stub: FakeCalendarClient,
    user: User,
    db: Session,
) -> None:
    service.connect(user, code="auth-code")
    account = db.query(ExternalCalendarAccount).one()
    account.access_token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    service.busy_intervals(user, at("2026-09-22 00:00"), at("2026-09-23 00:00"))

    assert client_stub.refresh_calls == 1
    db.refresh(account)
    assert decrypt(account.access_token_encrypted) == "access-2"


def test_valid_access_token_is_reused(
    service: ExternalCalendarService,
    client_stub: FakeCalendarClient,
    user: User,
) -> None:
    service.connect(user, code="auth-code")
    service.busy_intervals(user, at("2026-09-22 00:00"), at("2026-09-23 00:00"))

    assert client_stub.refresh_calls == 0


# ------------------------------------------------------- 空き時間への反映


def test_external_busy_time_is_excluded_from_free_time(
    db: Session, user: User
) -> None:
    """Google 側の予定も埋まっている時間として扱う。"""
    stub = FakeCalendarClient(
        busy=[BusyInterval(at("2026-09-22 13:00"), at("2026-09-22 15:00"))]
    )
    external = ExternalCalendarService(db, stub)
    external.connect(user, code="auth-code")

    slots = ScheduleService(db, external).find_free_time(
        user,
        period_start=at("2026-09-22 00:00"),
        period_end=at("2026-09-23 00:00"),
        minutes_needed=60,
    )

    ranges = [
        f"{s.start_at.astimezone(JST):%H:%M}-{s.end_at.astimezone(JST):%H:%M}"
        for s in slots
    ]
    assert ranges == ["09:00-13:00", "15:00-22:00"]


def test_internal_and_external_busy_times_are_merged(
    db: Session, user: User
) -> None:
    """内部と外部で重なる予定は1つにまとめて扱う。"""
    db.add(
        CalendarEvent(
            user_id=user.id,
            title="社内会議",
            start_at=at("2026-09-22 13:00"),
            end_at=at("2026-09-22 14:00"),
        )
    )
    db.flush()
    stub = FakeCalendarClient(
        busy=[BusyInterval(at("2026-09-22 13:30"), at("2026-09-22 16:00"))]
    )
    external = ExternalCalendarService(db, stub)
    external.connect(user, code="auth-code")

    slots = ScheduleService(db, external).find_free_time(
        user,
        period_start=at("2026-09-22 00:00"),
        period_end=at("2026-09-23 00:00"),
        minutes_needed=60,
    )

    ranges = [
        f"{s.start_at.astimezone(JST):%H:%M}-{s.end_at.astimezone(JST):%H:%M}"
        for s in slots
    ]
    assert ranges == ["09:00-13:00", "16:00-22:00"]


def test_free_time_still_works_when_google_fails(db: Session, user: User) -> None:
    """外部が落ちていても内部の空き時間計算は動く。"""

    class BrokenClient(FakeCalendarClient):
        def fetch_busy(self, access_token, start, end):
            from app.core.exceptions import BusinessRuleError

            raise BusinessRuleError("Google に接続できませんでした")

    external = ExternalCalendarService(db, BrokenClient())
    external.connect(user, code="auth-code")

    slots = ScheduleService(db, external).find_free_time(
        user,
        period_start=at("2026-09-22 00:00"),
        period_end=at("2026-09-23 00:00"),
        minutes_needed=60,
    )
    assert len(slots) == 1


def test_not_connected_user_is_unaffected(db: Session, user: User) -> None:
    external = ExternalCalendarService(db, FakeCalendarClient())

    assert external.busy_intervals(user, at("2026-09-22 00:00"), at("2026-09-23 00:00")) == []


# ------------------------------------------------------------------- API


@pytest.fixture
def api(db: Session, client_stub: FakeCalendarClient):
    app.dependency_overrides[get_external_calendar_service] = (
        lambda: ExternalCalendarService(db, client_stub)
    )
    yield
    app.dependency_overrides.pop(get_external_calendar_service, None)


def test_status_reports_not_connected(client: TestClient, api) -> None:
    body = client.get("/integrations").json()
    assert body == {
        "google_available": True,
        "google_connected": False,
        "google_account_email": None,
    }


def test_authorize_returns_consent_url(client: TestClient, api) -> None:
    body = client.get("/integrations/google/authorize").json()
    assert body["url"].startswith("https://example.com/consent")


def test_disconnect_requires_a_connection(client: TestClient, api) -> None:
    assert client.delete("/integrations/google").status_code == 404


def test_connection_is_disabled_without_credentials(
    client: TestClient, db: Session
) -> None:
    """認証情報が未設定なら連携機能は無効になる（アプリ自体は動く）。"""
    app.dependency_overrides[get_external_calendar_service] = (
        lambda: ExternalCalendarService(db, None)
    )
    try:
        assert client.get("/integrations").json()["google_available"] is False
        assert client.get("/integrations/google/authorize").status_code == 422
    finally:
        app.dependency_overrides.pop(get_external_calendar_service, None)
