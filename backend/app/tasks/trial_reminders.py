"""
Celery task for sending trial ending reminders.

Checks for trial subscriptions ending soon and sends notifications to help users
avoid unexpected charges.
"""

from datetime import datetime, timedelta, date
from typing import Tuple
from sqlalchemy import and_
from sqlalchemy.orm import Session
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.subscription import Subscription
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
    NotificationPriority,
)
from app.models.user import User
from app.services.email.templates.trial_reminder import generate_trial_reminder_email
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


def should_send_trial_reminder(
    subscription: Subscription, days_before: int, db: Session
) -> bool:
    """
    Check if we should send a trial reminder for this subscription.

    Args:
        subscription: The subscription to check
        days_before: Days before trial ends to send reminder
        db: Database session

    Returns:
        True if reminder should be sent
    """
    if not subscription.trial_end_date:
        return False

    # Only send reminders for active trials
    if subscription.trial_status not in ["trial", None]:
        return False

    # Calculate days until trial ends
    today = date.today()
    days_until_end = (subscription.trial_end_date - today).days

    # Only send if within the reminder window (3, 1, or 0 days before)
    if days_until_end != days_before:
        return False

    # Check if we already sent a reminder for this trial recently
    recent_reminder = (
        db.query(Notification)
        .filter(
            and_(
                Notification.user_id == subscription.user_id,
                Notification.related_subscription_id == subscription.id,
                Notification.type == NotificationType.TRIAL_ENDING,
                Notification.created_at >= datetime.now() - timedelta(days=1),
            )
        )
        .first()
    )

    if recent_reminder:
        logger.debug(f"Already sent trial reminder for subscription {subscription.id}")
        return False

    return True


def create_trial_notification(
    subscription: Subscription, days_before: int, db: Session
) -> Notification:
    """
    Create a trial ending reminder notification.

    Args:
        subscription: The subscription with trial ending
        days_before: Days before trial ends
        db: Database session

    Returns:
        Created notification
    """
    if days_before == 0:
        days_text = "today"
        urgency = "⚠️ URGENT"
        priority = NotificationPriority.HIGH
    elif days_before == 1:
        days_text = "tomorrow"
        urgency = "⚠️"
        priority = NotificationPriority.HIGH
    else:
        days_text = f"in {days_before} days"
        urgency = "⏰"
        priority = NotificationPriority.MEDIUM

    notification = Notification(
        user_id=subscription.user_id,
        related_subscription_id=subscription.id,
        type=NotificationType.TRIAL_ENDING,
        priority=priority,
        title=f"{urgency} {subscription.provider} Trial Ending",
        message=f"Your {subscription.provider} free trial ends {days_text} on {subscription.trial_end_date.strftime('%B %d, %Y')}. "
        f"You'll be charged {subscription.currency} {subscription.amount:.2f} unless you cancel.",
        notification_metadata={
            "trial_end_date": subscription.trial_end_date.isoformat(),
            "days_before": days_before,
            "amount": float(subscription.amount) if subscription.amount else None,
            "currency": subscription.currency,
            "billing_cycle": subscription.billing_cycle,
            "trial_status": subscription.trial_status,
        },
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(
        f"Created trial ending reminder for {subscription.provider} (user: {subscription.user_id}, days: {days_before})"
    )
    return notification


async def send_trial_email(
    notification: Notification, user: User, subscription: Subscription, db: Session
) -> Tuple[bool, str | None]:
    """
    Send trial ending reminder email.

    Args:
        notification: The notification
        user: User to send to
        subscription: The subscription with trial
        db: Database session

    Returns:
        (success, error_message)
    """
    days_until = (
        (subscription.trial_end_date - date.today()).days
        if subscription.trial_end_date
        else 0
    )

    if days_until == 0:
        urgency_title = "Today"
    elif days_until == 1:
        urgency_title = "Tomorrow"
    else:
        urgency_title = f"In {days_until} Days"
    subject = f"⚠️ {subscription.provider} Trial Ends {urgency_title}"

    html_content, plain_content = generate_trial_reminder_email(
        subscription_id=subscription.id,
        provider=subscription.provider,
        amount=subscription.amount,
        currency=subscription.currency,
        billing_cycle=subscription.billing_cycle,
        trial_end_date=subscription.trial_end_date,
        days_until=days_until,
    )

    # Send email
    email_service = EmailService(db)
    success, error = email_service.send_email(
        to_email=user.email,
        subject=subject,
        html_content=html_content,
        plain_content=plain_content,
    )

    # Update notification status
    notification.email_sent = success
    notification.email_sent_at = datetime.now() if success else None
    notification.email_error = error
    db.commit()

    if success:
        logger.info(
            f"Sent trial ending email to {user.email} for {subscription.provider}"
        )
    else:
        logger.error(f"Failed to send trial ending email to {user.email}: {error}")

    return success, error


@celery_app.task(name="tasks.check_trial_reminders")
def check_trial_reminders():
    """
    Check for trial subscriptions ending soon and send reminders.

    This task runs daily and:
    1. Gets all subscriptions with active trials
    2. Checks trial end dates
    3. Sends reminders at 3 days, 1 day, and 0 days (same day) before trial ends
    """
    db = None
    try:
        db = SessionLocal()
        logger.info("Starting trial ending reminders check...")

        # Days before trial ends to send reminders
        reminder_days = [3, 1, 0]  # 3 days before, 1 day before, day of

        total_reminders = 0
        total_emails = 0

        for days_before in reminder_days:
            # Get trial subscriptions ending on the target date
            target_date = date.today() + timedelta(days=days_before)

            subscriptions = (
                db.query(Subscription)
                .filter(
                    and_(
                        Subscription.is_active,
                        Subscription.trial_end_date == target_date,
                        Subscription.trial_status.in_(
                            ["trial", None]
                        ),  # Active trials only
                    )
                )
                .all()
            )

            logger.info(
                f"Found {len(subscriptions)} trials ending in {days_before} days"
            )

            for subscription in subscriptions:
                # Check user preferences for trial reminders
                pref = (
                    db.query(NotificationPreference)
                    .filter(
                        and_(
                            NotificationPreference.user_id == subscription.user_id,
                            NotificationPreference.notification_type
                            == NotificationType.TRIAL_ENDING,
                        )
                    )
                    .first()
                )

                # If no preference exists, default to enabled
                if pref is None or pref.enabled:
                    if should_send_trial_reminder(subscription, days_before, db):
                        # Create notification
                        notification = create_trial_notification(
                            subscription, days_before, db
                        )
                        total_reminders += 1

                        # Send email if enabled (default to True if no preference)
                        email_enabled = pref.email_enabled if pref else True
                        if email_enabled:
                            user = (
                                db.query(User)
                                .filter(User.id == subscription.user_id)
                                .first()
                            )
                            if user:
                                # Run async function synchronously in Celery task
                                import asyncio

                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                success, _ = loop.run_until_complete(
                                    send_trial_email(
                                        notification, user, subscription, db
                                    )
                                )
                                loop.close()

                                if success:
                                    total_emails += 1

        logger.info(
            f"Trial reminders check complete: {total_reminders} notifications created, {total_emails} emails sent"
        )
        return {
            "status": "success",
            "notifications_created": total_reminders,
            "emails_sent": total_emails,
        }

    except Exception as e:
        logger.error(f"Error in trial reminders task: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        if db is not None:
            db.close()
