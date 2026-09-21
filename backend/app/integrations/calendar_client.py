"""外部カレンダーのクライアント。

テストで差し替えられるよう Protocol で定義し、実装は Google 用のみ。
**予定のタイトルは取得しない。** 空き時間の計算に必要なのは「埋まっている時間帯」
だけなので、freeBusy API を使って最小限の情報だけを受け取る。
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx

from app.core.exceptions import BusinessRuleError

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
FREEBUSY_ENDPOINT = "https://www.googleapis.com/calendar/v3/freeBusy"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
#: 予定の閲覧に必要な最小の権限（書き込み権限は要求しない）
SCOPES = (
    "https://www.googleapis.com/auth/calendar.readonly "
    "https://www.googleapis.com/auth/userinfo.email"
)
REQUEST_TIMEOUT = 20.0


@dataclass(frozen=True)
class BusyInterval:
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    expires_at: datetime
    #: 再接続時など、返らないことがある
    refresh_token: str | None = None


class CalendarClient(Protocol):
    def authorize_url(self, redirect_uri: str, state: str) -> str: ...

    def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokens: ...

    def refresh_access_token(self, refresh_token: str) -> OAuthTokens: ...

    def fetch_account_email(self, access_token: str) -> str: ...

    def fetch_busy(
        self, access_token: str, start: datetime, end: datetime
    ) -> list[BusyInterval]: ...


class GoogleCalendarClient:
    """Google Calendar API を直接呼ぶ実装。"""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        params = httpx.QueryParams(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": SCOPES,
                # refresh token を得るために必要
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{AUTH_ENDPOINT}?{params}"

    def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokens:
        return self._request_tokens(
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
        )

    def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        return self._request_tokens(
            {
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            }
        )

    def fetch_account_email(self, access_token: str) -> str:
        data = self._get(USERINFO_ENDPOINT, access_token)
        return str(data.get("email", ""))

    def fetch_busy(
        self, access_token: str, start: datetime, end: datetime
    ) -> list[BusyInterval]:
        response = self._post(
            FREEBUSY_ENDPOINT,
            access_token,
            {
                "timeMin": start.astimezone(UTC).isoformat(),
                "timeMax": end.astimezone(UTC).isoformat(),
                "items": [{"id": "primary"}],
            },
        )
        periods = response.get("calendars", {}).get("primary", {}).get("busy", [])
        return [
            BusyInterval(
                start_at=datetime.fromisoformat(period["start"]),
                end_at=datetime.fromisoformat(period["end"]),
            )
            for period in periods
        ]

    # ----------------------------------------------------------------- 内部

    def _request_tokens(self, payload: dict[str, str]) -> OAuthTokens:
        try:
            response = httpx.post(
                TOKEN_ENDPOINT, data=payload, timeout=REQUEST_TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise BusinessRuleError("Google に接続できませんでした") from exc

        if response.status_code >= 400:
            raise BusinessRuleError(
                "Google の認証に失敗しました。接続をやり直してください"
            )

        data = response.json()
        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=int(data.get("expires_in", 3600))),
        )

    def _get(self, url: str, access_token: str) -> dict:
        return self._send("GET", url, access_token, None)

    def _post(self, url: str, access_token: str, body: dict) -> dict:
        return self._send("POST", url, access_token, body)

    def _send(
        self, method: str, url: str, access_token: str, body: dict | None
    ) -> dict:
        try:
            response = httpx.request(
                method,
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise BusinessRuleError("Google に接続できませんでした") from exc

        if response.status_code >= 400:
            raise BusinessRuleError(
                f"Google Calendar の取得に失敗しました（{response.status_code}）"
            )
        return response.json()
