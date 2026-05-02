"""
Celery task for monitoring subscription price changes.

Detects when subscription prices change and sends notifications to users.
"""

from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from decimal import Decimal
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
from app.services.email.templates.price_change import generate_price_change_email
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


def detect_price_change(
    subscription: Subscription, db: Session
) -> Tuple[bool, Decimal | None, Decimal | None]:
    """
    Detect if a subscription's price has changed.

    Uses extraction_metadata to track last known price.

    Args:
        subscription: The subscription to check
        db: Database session

    Returns:
        (has_changed, old_price, new_price)
    """
    if not subscription.amount:
        return False, None, None

    # Get last known price from extraction_metadata
    metadata = subscription.extraction_metadata or {}
    last_known_price = metadata.get("last_known_price")

    if last_known_price is None:
        # First time tracking - store current price
        metadata["last_known_price"] = float(subscription.amount)
        metadata["price_last_checked"] = datetime.now().isoformat()
        subscription.extraction_metadata = metadata
        db.commit()
        return False, None, None

    # Convert to Decimal for comparison
    last_price = Decimal(str(last_known_price))
    current_price = subscription.amount

    # Check if price changed
    if current_price != last_price:
        return True, last_price, current_price

    # Update last checked timestamp
    metadata["price_last_checked"] = datetime.now().isoformat()
    subscription.extraction_metadata = metadata
    db.commit()

    return False, None, None


def should_send_price_change_notification(
    subscription: Subscription, db: Session
) -> bool:
    """
    Check if we should send a price change notification.

    Args:
        subscription: The subscription with price change
        db: Database session

    Returns:
        True if notification should be sent
    """
    # Only send for active subscriptions
    if not subscription.is_active:
        return False

    # Check if we already sent a notification for this price change recently
    recent_notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == subscription.user_id,
            Notification.related_subscription_id == subscription.id,
            Notification.type == NotificationType.PRICE_CHANGE,
            Notification.created_at
            >= datetime.now() - timedelta(days=7),  # 7-day window
        )
        .first()
    )

    if recent_notification:
        logger.debug(
            f"Already sent price change notification for subscription {subscription.id}"
        )
        return False

    return True


def create_price_change_notification(
    subscription: Subscription, old_price: Decimal, new_price: Decimal, db: Session
) -> Notification:
    """
    Create a price change notification.

    Args:
        subscription: The subscription with price change
        old_price: Previous price
        new_price: New price
        db: Database session

    Returns:
        Created notification
    """
    price_diff = new_price - old_price
    is_increase = price_diff > 0
    change_percent = abs((price_diff / old_price) * 100)

    if is_increase:
        change_text = f"increased by {subscription.currency} {abs(price_diff):.2f}"
        icon = "📈"
        priority = (
            NotificationPriority.HIGH
            if change_percent > 20
            else NotificationPriority.MEDIUM
        )
    else:
        change_text = f"decreased by {subscription.currency} {abs(price_diff):.2f}"
        icon = "📉"
        priority = NotificationPriority.LOW

    notification = Notification(
        user_id=subscription.user_id,
        related_subscription_id=subscription.id,
        type=NotificationType.PRICE_CHANGE,
        priority=priority,
        title=f"{icon} {subscription.provider} Price Change",
        message=f"The price for {subscription.provider} has {change_text}. "
        f"New price: {subscription.currency} {new_price:.2f} (was {subscription.currency} {old_price:.2f}).",
        notification_metadata={
            "old_price": float(old_price),
            "new_price": float(new_price),
            "price_difference": float(price_diff),
            "change_percent": float(change_percent),
            "is_increase": is_increase,
            "currency": subscription.currency,
        },
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(
        f"Created price change notification for {subscription.provider} (user: {subscription.user_id})"
    )
    return notification


async def send_price_change_email(
    notification: Notification, user: User, subscription: Subscription, db: Session
) -> Tuple[bool, str | None]:
    """
    Send price change notification email.

    Args:
        notification: The notification
        user: User to send to
        subscription: The subscription
        db: Database session

    Returns:
        (success, error_message)
    """
    metadata = notification.notification_metadata
    old_price = Decimal(str(metadata.get("old_price", 0)))
    new_price = Decimal(str(metadata.get("new_price", 0)))
    price_diff = Decimal(str(metadata.get("price_difference", 0)))
    change_percent = metadata.get("change_percent", 0)
    is_increase = metadata.get("is_increase", True)

    change_icon = "📈" if is_increase else "📉"
    change_word = "Increased" if is_increase else "Decreased"
    subject = f"{change_icon} {subscription.provider} Price {change_word}"

    html_content, plain_content = generate_price_change_email(
        subscription_id=subscription.id,
        provider=subscription.provider,
        currency=subscription.currency,
        billing_cycle=subscription.billing_cycle,
        old_price=old_price,
        new_price=new_price,
        price_diff=price_diff,
        change_percent=change_percent,
        is_increase=is_increase,
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
            f"Sent price change email to {user.email} for {subscription.provider}"
        )
    else:
        logger.error(f"Failed to send price change email to {user.email}: {error}")

    return success, error


@celery_app.task(name="tasks.check_price_changes")
def check_price_changes():
    """
    Check for subscription price changes and send notifications.

    This task runs periodically (e.g., daily or when prices are updated) and:
    1. Gets all active subscriptions
    2. Checks if prices have changed since last check
    3. Sends notifications for price changes
    """
    db = None
    try:
        db = SessionLocal()
        logger.info("Starting price change monitoring...")

        # Get all active subscriptions with prices
        subscriptions = (
            db.query(Subscription)
            .filter(Subscription.is_active, Subscription.amount.isnot(None))
            .all()
        )

        logger.info(f"Checking {len(subscriptions)} subscriptions for price changes")

        total_changes = 0
        total_notifications = 0
        total_emails = 0

        for subscription in subscriptions:
            # Detect price change
            has_changed, old_price, new_price = detect_price_change(subscription, db)

            if has_changed:
                total_changes += 1
                logger.info(
                    f"Price change detected for {subscription.provider}: {old_price} → {new_price}"
                )

                # Check user preferences
                pref = (
                    db.query(NotificationPreference)
                    .filter(
                        NotificationPreference.user_id == subscription.user_id,
                        NotificationPreference.notification_type
                        == NotificationType.PRICE_CHANGE,
                    )
                    .first()
                )

                # Default to enabled if no preference exists, otherwise respect the preference
                if pref is None or pref.enabled:
                    if should_send_price_change_notification(subscription, db):
                        # Create notification
                        notification = create_price_change_notification(
                            subscription, old_price, new_price, db
                        )
                        total_notifications += 1

                        # Send email if enabled
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
                                    send_price_change_email(
                                        notification, user, subscription, db
                                    )
                                )
                                loop.close()

                                if success:
                                    total_emails += 1

                        # Update last known price after notification
                        metadata = subscription.extraction_metadata or {}
                        metadata["last_known_price"] = float(new_price)
                        metadata["price_change_detected_at"] = (
                            datetime.now().isoformat()
                        )
                        subscription.extraction_metadata = metadata
                        # Mark the JSONB column as modified so SQLAlchemy tracks the change
                        flag_modified(subscription, "extraction_metadata")
                        db.commit()

        logger.info(
            f"Price monitoring complete: {total_changes} changes detected, "
            f"{total_notifications} notifications created, {total_emails} emails sent"
        )
        return {
            "status": "success",
            "price_changes_detected": total_changes,
            "notifications_created": total_notifications,
            "emails_sent": total_emails,
        }

    except Exception as e:
        logger.error(f"Error in price change monitoring task: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        if db is not None:
            db.close()
