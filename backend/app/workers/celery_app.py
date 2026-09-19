"""Celery application factory."""

from celery import Celery
from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "revenue_recovery",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    # Beat schedule: run attribution scan every N seconds
    beat_schedule={
        "attribution-scan": {
            "task": "app.workers.tasks.run_attribution_scan_all_merchants",
            "schedule": settings.ATTRIBUTION_SCAN_INTERVAL,
        },
    },
)
