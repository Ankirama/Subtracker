"""
Celery tasks for sending weekly and monthly subscription summaries.

Generates comprehensive spending reports and sends them via email based on user preferences.
"""

from datetime import datetime
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
    NotificationPriority,
)
from app.models.user import User
from app.services.summary_service import SummaryService
from app.services.email_templates import EmailTemplates
from app.services.email_service import EmailService
from app.config import settings
from app.utils.config_helper import get_config_value

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_weekly_summaries")
def send_weekly_summaries():
    """
    Send weekly subscription summaries to all users who have it enabled.

    Scheduled to run every Monday morning.
    """
    db = SessionLocal()
    try:
        logger.info("Starting weekly summary task")

        # Get current day of week (0 = Monday, 6 = Sunday)
        current_day_of_week = datetime.now().weekday()

        # Get all users with weekly summary enabled
        preferences = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.notification_type
                == NotificationType.WEEKLY_SUMMARY,
                NotificationPreference.enabled,
                NotificationPreference.summary_day_of_week == current_day_of_week,
            )
            .all()
        )

        logger.info(
            f"Found {len(preferences)} users with weekly summaries enabled for day {current_day_of_week}"
        )

        sent_count = 0
        error_count = 0

        for pref in preferences:
            try:
                user = db.query(User).filter(User.id == pref.user_id).first()
                if not user:
                    continue

                # Generate summary
                summary_data = SummaryService.generate_weekly_summary(db, user)

                # Create in-app notification if enabled
                if pref.in_app_enabled:
                    notification = Notification(
                        user_id=user.id,
                        type=NotificationType.WEEKLY_SUMMARY,
                        priority=NotificationPriority.LOW,
                        title="📊 Your Weekly Subscription Summary",
                        message=f"Total spending: €{summary_data['total_monthly_cost']:.2f}/mo • {summary_data['total_subscriptions']} active subscriptions",
                        notification_metadata=summary_data,
                    )
                    db.add(notification)
                    db.commit()

                # Send email if enabled
                if pref.email_enabled and user.email:
                    try:
                        # Get configured frontend URL for email links
                        frontend_url = get_config_value(
                            "frontend_url", settings.FRONTEND_URL, db
                        )
                        html_content = EmailTemplates.generate_summary_email(
                            summary_data, frontend_url
                        )

                        email_service = EmailService()
                        email_service.send_email(
                            to_email=user.email,
                            subject=f"📊 Your Weekly Subscription Summary - €{summary_data['total_monthly_cost']:.2f}/mo",
                            html_content=html_content,
                        )

                        # Update notification with email status
                        if pref.in_app_enabled:
                            notification.email_sent = True
                            notification.email_sent_at = datetime.now()
                            db.commit()

                        logger.info(f"Sent weekly summary to {user.email}")
                        sent_count += 1

                    except Exception as e:
                        logger.error(f"Failed to send email to {user.email}: {str(e)}")
                        if pref.in_app_enabled:
                            notification.email_error = str(e)
                            db.commit()
                        error_count += 1

            except Exception as e:
                logger.error(
                    f"Error processing weekly summary for user {pref.user_id}: {str(e)}"
                )
                error_count += 1
                continue

        logger.info(
            f"Weekly summary task completed: {sent_count} sent, {error_count} errors"
        )
        return {"sent": sent_count, "errors": error_count}

    except Exception as e:
        logger.error(f"Fatal error in weekly summary task: {str(e)}")
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.send_monthly_summaries")
def send_monthly_summaries():
    """
    Send monthly subscription summaries to all users who have it enabled.

    Scheduled to run on the 1st day of each month.
    """
    db = SessionLocal()
    try:
        logger.info("Starting monthly summary task")

        # Get current day of month
        current_day_of_month = datetime.now().day

        # Get all users with monthly summary enabled
        preferences = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.notification_type
                == NotificationType.MONTHLY_SUMMARY,
                NotificationPreference.enabled,
                NotificationPreference.summary_day_of_month == current_day_of_month,
            )
            .all()
        )

        logger.info(
            f"Found {len(preferences)} users with monthly summaries enabled for day {current_day_of_month}"
        )

        sent_count = 0
        error_count = 0

        for pref in preferences:
            try:
                user = db.query(User).filter(User.id == pref.user_id).first()
                if not user:
                    continue

                # Generate summary
                summary_data = SummaryService.generate_monthly_summary(db, user)

                # Create in-app notification if enabled
                if pref.in_app_enabled:
                    notification = Notification(
                        user_id=user.id,
                        type=NotificationType.MONTHLY_SUMMARY,
                        priority=NotificationPriority.LOW,
                        title="📈 Your Monthly Subscription Summary",
                        message=f"Total spending: €{summary_data['total_monthly_cost']:.2f}/mo • {summary_data['new_subscriptions_count']} new, {summary_data['cancelled_subscriptions_count']} cancelled",
                        notification_metadata=summary_data,
                    )
                    db.add(notification)
                    db.commit()

                # Send email if enabled
                if pref.email_enabled and user.email:
                    try:
                        # Get configured frontend URL for email links
                        frontend_url = get_config_value(
                            "frontend_url", settings.FRONTEND_URL, db
                        )
                        html_content = EmailTemplates.generate_summary_email(
                            summary_data, frontend_url
                        )

                        email_service = EmailService()
                        email_service.send_email(
                            to_email=user.email,
                            subject=f"📈 Your Monthly Subscription Summary - €{summary_data['total_monthly_cost']:.2f}/mo",
                            html_content=html_content,
                        )

                        # Update notification with email status
                        if pref.in_app_enabled:
                            notification.email_sent = True
                            notification.email_sent_at = datetime.now()
                            db.commit()

                        logger.info(f"Sent monthly summary to {user.email}")
                        sent_count += 1

                    except Exception as e:
                        logger.error(f"Failed to send email to {user.email}: {str(e)}")
                        if pref.in_app_enabled:
                            notification.email_error = str(e)
                            db.commit()
                        error_count += 1

            except Exception as e:
                logger.error(
                    f"Error processing monthly summary for user {pref.user_id}: {str(e)}"
                )
                error_count += 1
                continue

        logger.info(
            f"Monthly summary task completed: {sent_count} sent, {error_count} errors"
        )
        return {"sent": sent_count, "errors": error_count}

    except Exception as e:
        logger.error(f"Fatal error in monthly summary task: {str(e)}")
        raise
    finally:
        db.close()
