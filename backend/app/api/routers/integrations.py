from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, DbSession, ExternalCalendarServiceDep
from app.core.config import get_settings
from app.schemas.integration import AuthorizeUrl, IntegrationStatus

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=IntegrationStatus)
def status_(user: CurrentUser, service: ExternalCalendarServiceDep) -> IntegrationStatus:
    """外部カレンダーの連携状況を返す。"""
    accounts = service.list_accounts(user)
    return IntegrationStatus(
        google_available=service.available,
        google_connected=bool(accounts),
        google_account_email=accounts[0].account_email if accounts else None,
        google_needs_reauth=bool(accounts and accounts[0].reauth_required),
    )


@router.get("/google/authorize", response_model=AuthorizeUrl)
def authorize(user: CurrentUser, service: ExternalCalendarServiceDep) -> AuthorizeUrl:
    """Google の同意画面URLを返す。画面はここへ遷移させる。"""
    return AuthorizeUrl(url=service.authorize_url(user))


@router.get("/google/callback")
def callback(
    code: str,
    state: str,
    db: DbSession,
    service: ExternalCalendarServiceDep,
) -> RedirectResponse:
    """Google からの戻り先。

    ログイン中のユーザーではなく **state に署名されたユーザー** を使う。
    細工したコールバックを踏ませて別アカウントを紐づけられるのを防ぐ。
    """
    from app.models.user import User

    settings = get_settings()
    user_id = service.user_id_from_state(state)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        return RedirectResponse(
            f"{settings.frontend_base_url}/?google=invalid_state", status_code=303
        )

    try:
        service.connect(user, code)
    except Exception:  # noqa: BLE001 - 失敗は画面で伝える
        return RedirectResponse(
            f"{settings.frontend_base_url}/?google=failed", status_code=303
        )

    return RedirectResponse(
        f"{settings.frontend_base_url}/?google=connected", status_code=303
    )


@router.delete("/google", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(user: CurrentUser, service: ExternalCalendarServiceDep) -> None:
    """連携を解除する（保存したトークンを削除する）。"""
    service.disconnect(user)
