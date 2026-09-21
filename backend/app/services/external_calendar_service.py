from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.security import ALGORITHM
from app.integrations.calendar_client import BusyInterval, CalendarClient
from app.models.enums import CalendarProvider
from app.models.external_calendar import ExternalCalendarAccount
from app.models.user import User

#: 接続手続きの途中で使う state の有効期間
STATE_TTL_MINUTES = 10
#: アクセストークンの期限がこれより近ければ先に更新する
REFRESH_MARGIN_SECONDS = 60


class ExternalCalendarService:
    """外部カレンダーとの連携。

    現在は読み取りのみ。取り込むのは「埋まっている時間帯」だけで、
    予定の内容は取得しない。
    """

    def __init__(self, db: Session, client: CalendarClient | None) -> None:
        self.db = db
        self.client = client

    # ------------------------------------------------------------ 接続手続き

    @property
    def available(self) -> bool:
        """連携が使える設定になっているか。"""
        return self.client is not None

    def _require_client(self) -> CalendarClient:
        if self.client is None:
            raise BusinessRuleError(
                "Google 連携が設定されていません（GOOGLE_CLIENT_ID 等を確認してください）"
            )
        return self.client

    def authorize_url(self, user: User) -> str:
        """同意画面のURLを作る。

        state には署名付きの短命トークンを入れる。
        これがないと、他人が細工したコールバックを踏ませて
        別アカウントを紐づけられてしまう（CSRF）。
        """
        settings = get_settings()
        state = jwt.encode(
            {
                "sub": str(user.id),
                "purpose": "google_calendar_connect",
                "exp": datetime.now(UTC) + timedelta(minutes=STATE_TTL_MINUTES),
            },
            settings.secret_key,
            algorithm=ALGORITHM,
        )
        return self._require_client().authorize_url(
            settings.google_redirect_uri, state
        )

    def user_id_from_state(self, state: str) -> int | None:
        try:
            payload = jwt.decode(
                state, get_settings().secret_key, algorithms=[ALGORITHM]
            )
        except jwt.InvalidTokenError:
            return None
        if payload.get("purpose") != "google_calendar_connect":
            return None
        try:
            return int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return None

    def connect(self, user: User, code: str) -> ExternalCalendarAccount:
        client = self._require_client()
        tokens = client.exchange_code(code, get_settings().google_redirect_uri)
        if tokens.refresh_token is None:
            raise BusinessRuleError(
                "Google から再接続用のトークンを取得できませんでした。"
                "Google アカウントの連携を一度解除してからやり直してください"
            )

        account = self._find(user.id) or ExternalCalendarAccount(
            user_id=user.id, provider=CalendarProvider.GOOGLE
        )
        account.account_email = client.fetch_account_email(tokens.access_token)
        account.refresh_token_encrypted = encrypt(tokens.refresh_token)
        account.access_token_encrypted = encrypt(tokens.access_token)
        account.access_token_expires_at = tokens.expires_at
        account.reauth_required = False

        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def disconnect(self, user: User) -> None:
        account = self._find(user.id)
        if account is None:
            raise NotFoundError("連携アカウント", "google")
        self.db.delete(account)
        self.db.commit()

    def list_accounts(self, user: User) -> list[ExternalCalendarAccount]:
        account = self._find(user.id)
        return [account] if account else []

    # -------------------------------------------------------------- 予定取得

    def busy_intervals(
        self, user: User, start: datetime, end: datetime
    ) -> list[BusyInterval]:
        """外部カレンダーで埋まっている時間帯。

        連携していない・設定が無い・取得に失敗した場合は空を返す。
        **外部が落ちていても内部の空き時間計算は動くべき**なので、
        ここで例外を外に出さない。
        """
        account = self._find(user.id)
        if account is None or self.client is None:
            return []

        try:
            access_token = self._valid_access_token(account)
            if access_token is None:
                return []
            return self.client.fetch_busy(access_token, start, end)
        except BusinessRuleError:
            return []

    def _valid_access_token(self, account: ExternalCalendarAccount) -> str | None:
        """期限が近ければ更新してから返す。"""
        expires_at = account.access_token_expires_at
        token = (
            decrypt(account.access_token_encrypted)
            if account.access_token_encrypted
            else None
        )
        if (
            token
            and expires_at
            and expires_at - datetime.now(UTC) > timedelta(seconds=REFRESH_MARGIN_SECONDS)
        ):
            return token

        refresh_token = decrypt(account.refresh_token_encrypted)
        if refresh_token is None or self.client is None:
            self._mark_reauth_required(account)
            return None

        try:
            tokens = self.client.refresh_access_token(refresh_token)
        except BusinessRuleError:
            # テストモードの OAuth クライアントは更新トークンが7日で失効する。
            # 黙って無視すると「なぜか予定が考慮されない」状態になるため記録し、
            # 画面で再連携を促せるようにする
            self._mark_reauth_required(account)
            return None

        account.access_token_encrypted = encrypt(tokens.access_token)
        account.access_token_expires_at = tokens.expires_at
        account.reauth_required = False
        if tokens.refresh_token:
            account.refresh_token_encrypted = encrypt(tokens.refresh_token)
        self.db.commit()
        return tokens.access_token

    def _mark_reauth_required(self, account: ExternalCalendarAccount) -> None:
        if not account.reauth_required:
            account.reauth_required = True
            self.db.commit()

    def _find(self, user_id: int) -> ExternalCalendarAccount | None:
        stmt = select(ExternalCalendarAccount).where(
            ExternalCalendarAccount.user_id == user_id,
            ExternalCalendarAccount.provider == CalendarProvider.GOOGLE,
        )
        return self.db.execute(stmt).scalar_one_or_none()
