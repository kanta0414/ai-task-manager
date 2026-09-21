from fastapi import APIRouter

from app.api.deps import CurrentUser, NotificationServiceDep
from app.models.notification import Notification
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    user: CurrentUser,
    service: NotificationServiceDep,
    unread_only: bool = False,
) -> list[Notification]:
    """バックグラウンド処理が作った通知を返す。"""
    return service.list_for_user(user, unread_only=unread_only)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: int, user: CurrentUser, service: NotificationServiceDep
) -> Notification:
    """通知を既読にする。"""
    return service.mark_read(user, notification_id)
