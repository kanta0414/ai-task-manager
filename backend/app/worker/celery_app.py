from pathlib import Path

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_task_manager",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend or None,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    timezone=settings.timezone,
    enable_utc=True,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
    beat_schedule={
        # まもなく始まる予定を知らせる（開始30分前に拾えるよう5分間隔）
        "send-due-reminders": {
            "task": "app.worker.tasks.send_due_reminders",
            "schedule": crontab(minute="*/5"),
        },
        # 朝にその日の予定と期限をまとめる
        "daily-digest": {
            "task": "app.worker.tasks.create_daily_digest",
            "schedule": crontab(hour=7, minute=0),
        },
        # 夜に終わらなかった作業を知らせる
        "nightly-unfinished-check": {
            "task": "app.worker.tasks.flag_unfinished_work",
            "schedule": crontab(hour=23, minute=0),
        },
    },
)

# Redis を用意できない環境向け。kombu の filesystem トランスポートは
# 置き場所の指定が必須なので、ここで作って渡す。
if settings.celery_broker_url.startswith("filesystem://"):
    folder = Path(settings.celery_broker_folder).resolve()
    processed = folder / "processed"
    folder.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    celery_app.conf.broker_transport_options = {
        "data_folder_in": str(folder),
        "data_folder_out": str(folder),
        "data_folder_processed": str(processed),
    }
