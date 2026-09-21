"""定期実行タスク。

**処理の中身は Service 側にある。** ここはセッションを用意して呼ぶだけに保ち、
ブローカーが無い環境でも Service を直接テストできるようにする。
"""

import logging
from datetime import UTC, datetime

from app.db.session import session_scope
from app.services.notification_service import NotificationService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.send_due_reminders")
def send_due_reminders() -> int:
    with session_scope() as db:
        created = NotificationService(db).send_due_reminders(datetime.now(UTC))
    logger.info("reminders created: %s", created)
    return created


@celery_app.task(name="app.worker.tasks.create_daily_digest")
def create_daily_digest() -> int:
    with session_scope() as db:
        created = NotificationService(db).create_daily_digest(datetime.now(UTC))
    logger.info("daily digests created: %s", created)
    return created


@celery_app.task(name="app.worker.tasks.flag_unfinished_work")
def flag_unfinished_work() -> int:
    with session_scope() as db:
        created = NotificationService(db).flag_unfinished_work(datetime.now(UTC))
    logger.info("unfinished notifications created: %s", created)
    return created
