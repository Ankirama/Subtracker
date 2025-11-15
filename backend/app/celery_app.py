"""
Celery application configuration for async task processing.
"""
from celery import Celery
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "subscription_tracker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.email_sync"]  # Task modules to import
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (memory management)
    worker_prefetch_multiplier=4,  # Number of tasks to prefetch
    task_acks_late=True,  # Acknowledge tasks after completion (safer)
    task_reject_on_worker_lost=True,  # Reject tasks if worker dies
)

# Task routes (use default 'celery' queue for now)
# celery_app.conf.task_routes = {
#     "app.tasks.email_sync.*": {"queue": "email_processing"},
# }

# Celery Beat schedule for periodic tasks (Phase 2)
celery_app.conf.beat_schedule = {
    # Will add periodic sync tasks in Phase 2
}

logger.info("Celery app initialized")
