"""
Celery task for sending subscription renewal reminders.

Checks for upcoming subscription renewals and sends notifications based on user preferences.
"""
from datetime import datetime, timedelta, date
from typing import List, Tuple
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.subscription import Subscription
from app.models.notification import Notification, NotificationPreference, NotificationType, NotificationPriority
from app.models.user import User
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


def get_renewal_date(subscription: Subscription) -> date | None:
    """
    Get the next renewal date for a subscription.

    Returns:
        The next billing date, or renewal date if billing date not set
    """
    return subscription.next_billing_date or subscription.renewal_date


def should_send_reminder(
    subscription: Subscription,
    days_before: int,
    db: Session
) -> bool:
    """
    Check if we should send a reminder for this subscription.

    Args:
        subscription: The subscription to check
        days_before: Days before renewal to send reminder
        db: Database session

    Returns:
        True if reminder should be sent
    """
    renewal_date = get_renewal_date(subscription)
    if not renewal_date:
        return False

    # Calculate target date for reminder
    today = date.today()
    days_until_renewal = (renewal_date - today).days

    # Only send if within the reminder window
    if days_until_renewal != days_before:
        return False

    # Check if we already sent a reminder for this renewal period
    # Look for notifications created in the last 24 hours for this subscription
    recent_reminder = db.query(Notification).filter(
        and_(
            Notification.user_id == subscription.user_id,
            Notification.related_subscription_id == subscription.id,
            Notification.type == NotificationType.RENEWAL_REMINDER,
            Notification.created_at >= datetime.now() - timedelta(days=1)
        )
    ).first()

    if recent_reminder:
        logger.debug(f"Already sent reminder for subscription {subscription.id}")
        return False

    return True


def create_renewal_notification(
    subscription: Subscription,
    days_before: int,
    db: Session
) -> Notification:
    """
    Create a renewal reminder notification.

    Args:
        subscription: The subscription to remind about
        days_before: Days before renewal
        db: Database session

    Returns:
        Created notification
    """
    renewal_date = get_renewal_date(subscription)
    days_text = f"{days_before} days" if days_before > 1 else "tomorrow"

    notification = Notification(
        user_id=subscription.user_id,
        related_subscription_id=subscription.id,
        type=NotificationType.RENEWAL_REMINDER,
        priority=NotificationPriority.MEDIUM,
        title=f"{subscription.provider} Renewal Reminder",
        message=f"Your {subscription.provider} subscription will renew in {days_text} on {renewal_date.strftime('%B %d, %Y')}. "
                f"Amount: {subscription.currency} {subscription.amount:.2f}",
        notification_metadata={
            "renewal_date": renewal_date.isoformat(),
            "days_before": days_before,
            "amount": float(subscription.amount) if subscription.amount else None,
            "currency": subscription.currency,
            "billing_cycle": subscription.billing_cycle
        }
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(f"Created renewal reminder for {subscription.provider} (user: {subscription.user_id})")
    return notification


async def send_renewal_email(
    notification: Notification,
    user: User,
    subscription: Subscription,
    db: Session
) -> Tuple[bool, str | None]:
    """
    Send renewal reminder email.

    Args:
        notification: The notification
        user: User to send to
        subscription: The subscription
        db: Database session

    Returns:
        (success, error_message)
    """
    renewal_date = get_renewal_date(subscription)
    days_until = (renewal_date - date.today()).days if renewal_date else 0

    # Build email content
    subject = f"⏰ {subscription.provider} Renews in {days_until} Days"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">🔔 Renewal Reminder</h2>
            <p style="font-size: 16px; color: #34495e;">
                Your <strong>{subscription.provider}</strong> subscription will renew soon.
            </p>
        </div>

        <div style="background-color: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="color: #2c3e50; margin-top: 0;">Subscription Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Provider:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">{subscription.provider}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Amount:</strong></td>
                    <td style="padding: 10px 0; text-align: right; color: #e74c3c; font-size: 18px;">
                        <strong>{subscription.currency} {subscription.amount:.2f}</strong>
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Billing Cycle:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">{subscription.billing_cycle.capitalize()}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Renewal Date:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">
                        <strong>{renewal_date.strftime('%B %d, %Y')}</strong> ({days_until} days)
                    </td>
                </tr>
            </table>
        </div>

        <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
            <p style="margin: 0; color: #856404;">
                💡 <strong>Reminder:</strong> You have {days_until} days to cancel or modify this subscription if needed.
            </p>
        </div>

        <div style="text-align: center; margin-top: 30px;">
            <a href="http://localhost:5173/subscriptions/{subscription.id}"
               style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Subscription
            </a>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #95a5a6; font-size: 12px;">
            <p>
                You're receiving this because you have renewal reminders enabled.<br>
                <a href="http://localhost:5173/notifications/settings" style="color: #3498db;">Manage notification settings</a>
            </p>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
Renewal Reminder

Your {subscription.provider} subscription will renew in {days_until} days.

Subscription Details:
- Provider: {subscription.provider}
- Amount: {subscription.currency} {subscription.amount:.2f}
- Billing Cycle: {subscription.billing_cycle.capitalize()}
- Renewal Date: {renewal_date.strftime('%B %d, %Y')}

You have {days_until} days to cancel or modify this subscription if needed.

View subscription: http://localhost:5173/subscriptions/{subscription.id}
Manage settings: http://localhost:5173/notifications/settings
    """

    # Send email
    email_service = EmailService(db)
    success, error = email_service.send_email(
        to_email=user.email,
        subject=subject,
        html_content=html_content,
        plain_content=plain_content
    )

    # Update notification status
    notification.email_sent = success
    notification.email_sent_at = datetime.now() if success else None
    notification.email_error = error
    db.commit()

    if success:
        logger.info(f"Sent renewal email to {user.email} for {subscription.provider}")
    else:
        logger.error(f"Failed to send renewal email to {user.email}: {error}")

    return success, error


@celery_app.task(name="tasks.check_renewal_reminders")
def check_renewal_reminders():
    """
    Check for upcoming subscription renewals and send reminders.

    This task runs daily and:
    1. Gets all active subscriptions with renewal dates
    2. Checks user notification preferences
    3. Sends reminders for subscriptions due within configured days
    """
    db = None
    try:
        db = SessionLocal()
        logger.info("Starting renewal reminders check...")

        # Get all renewal reminder preferences
        preferences = db.query(NotificationPreference).filter(
            and_(
                NotificationPreference.notification_type == NotificationType.RENEWAL_REMINDER,
                NotificationPreference.enabled == True
            )
        ).all()

        total_reminders = 0
        total_emails = 0

        for pref in preferences:
            days_before = pref.days_before_renewal or 3  # Default 3 days

            # Get active subscriptions for this user with upcoming renewals
            subscriptions = db.query(Subscription).filter(
                and_(
                    Subscription.user_id == pref.user_id,
                    Subscription.is_active == True,
                    or_(
                        Subscription.next_billing_date.isnot(None),
                        Subscription.renewal_date.isnot(None)
                    )
                )
            ).all()

            for subscription in subscriptions:
                if should_send_reminder(subscription, days_before, db):
                    # Create notification
                    notification = create_renewal_notification(subscription, days_before, db)
                    total_reminders += 1

                    # Send email if enabled
                    if pref.email_enabled:
                        user = db.query(User).filter(User.id == pref.user_id).first()
                        if user:
                            # Run async function synchronously in Celery task
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            success, _ = loop.run_until_complete(
                                send_renewal_email(notification, user, subscription, db)
                            )
                            loop.close()

                            if success:
                                total_emails += 1

        logger.info(f"Renewal reminders check complete: {total_reminders} notifications created, {total_emails} emails sent")
        return {
            "status": "success",
            "notifications_created": total_reminders,
            "emails_sent": total_emails
        }

    except Exception as e:
        logger.error(f"Error in renewal reminders task: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        if db is not None:
            db.close()
