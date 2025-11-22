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
    include=[
        "app.tasks.email_sync",
        "app.tasks.notifications",
        "app.tasks.renewal_reminders",  # Renewal reminder tasks
        "app.tasks.trial_reminders",  # Trial ending reminder tasks
        "app.tasks.summary_tasks",  # Weekly/monthly summary tasks
        "app.tasks.price_change_monitor",  # Price change monitoring
        "app.tasks.system_announcements",  # System announcements
        "app.tasks.email_verification",  # Email verification cleanup tasks
        "app.tasks.budget_alerts"  # Budget alert monitoring
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=None,  # No time limit - task completes when pagination finishes
    task_soft_time_limit=None,  # No soft time limit - relies on natural completion
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (memory management)
    worker_prefetch_multiplier=4,  # Number of tasks to prefetch
    task_acks_late=True,  # Acknowledge tasks after completion (safer)
    task_reject_on_worker_lost=True,  # Reject tasks if worker dies
    beat_schedule_filename="/tmp/celerybeat-schedule",  # Writable location for beat schedule
    broker_connection_retry_on_startup=True,  # Retry broker connection on startup (Celery 6.0+)
)

# Task routes (use default 'celery' queue for now)
# celery_app.conf.task_routes = {
#     "app.tasks.email_sync.*": {"queue": "email_processing"},
# }

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Notification tasks
    "check-renewal-reminders": {
        "task": "tasks.check_renewal_reminders",
        "schedule": 86400.0,  # Run daily at midnight UTC
    },
    "check-trial-reminders": {
        "task": "tasks.check_trial_reminders",
        "schedule": 86400.0,  # Run daily to check trial endings (3 days, 1 day, same day)
    },
    "send-weekly-summaries": {
        "task": "tasks.send_weekly_summaries",
        "schedule": 86400.0,  # Run daily (will check if it's the right day)
    },
    "send-monthly-summaries": {
        "task": "tasks.send_monthly_summaries",
        "schedule": 86400.0,  # Run daily (will check if it's the right day)
    },
    "check-inactive-subscriptions": {
        "task": "tasks.check_inactive_subscriptions",
        "schedule": 604800.0,  # Run weekly (every 7 days)
    },
    "check-price-changes": {
        "task": "tasks.check_price_changes",
        "schedule": 86400.0,  # Run daily to monitor subscription price changes
    },
    # Email verification cleanup
    "cleanup-unverified-users": {
        "task": "tasks.cleanup_unverified_users",
        "schedule": 86400.0,  # Run daily at 2 AM UTC to delete unverified accounts older than 7 days
    },
    # Budget monitoring
    "check-budget-alerts": {
        "task": "app.tasks.budget_alerts.check_budget_alerts",
        "schedule": 86400.0,  # Run daily to check budgets and send alerts
    },
}

logger.info("Celery app initialized")
