"""Shared worker and singleton beat entry point."""

from celery import Celery

from app.config import get_settings
from app.integrations.jobs import configure_jobs

settings = get_settings()
celery_app = Celery("kairos", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    imports=["app.auth.tasks"],
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)


configure_jobs(celery_app)
