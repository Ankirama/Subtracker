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

    # Styling based on price change direction
    if is_increase:
        change_color = "#e53e3e"
        change_icon = "📈"
        change_word = "Increased"
        banner_style = "background-color: #fed7d7; border: 2px solid #fc8181;"
    else:
        change_color = "#38a169"
        change_icon = "📉"
        change_word = "Decreased"
        banner_style = "background-color: #c6f6d5; border: 2px solid #68d391;"

    # Build email content
    subject = f"{change_icon} {subscription.provider} Price {change_word}"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Price Change Banner -->
        <div style="{banner_style} padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 24px; color: {change_color};">
                {change_icon} PRICE {change_word.upper()}
            </h1>
        </div>

        <div style="background-color: #fff; border: 2px solid {change_color}; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">💰 {subscription.provider} Price Update</h2>
            <p style="font-size: 16px; color: #34495e;">
                The subscription price for <strong>{subscription.provider}</strong> has changed.
            </p>
        </div>

        <div style="background-color: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="color: #2c3e50; margin-top: 0;">Price Comparison</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Previous Price:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">
                        <span style="text-decoration: line-through; color: #95a5a6;">
                            {subscription.currency} {old_price:.2f}
                        </span>
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>New Price:</strong></td>
                    <td style="padding: 10px 0; text-align: right; color: {change_color}; font-size: 20px;">
                        <strong>{subscription.currency} {new_price:.2f}</strong>
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Change:</strong></td>
                    <td style="padding: 10px 0; text-align: right; color: {change_color};">
                        <strong>{'+' if is_increase else ''}{subscription.currency} {price_diff:.2f} ({change_percent:.1f}%)</strong>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Billing Cycle:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">{subscription.billing_cycle.capitalize()}</td>
                </tr>
            </table>
        </div>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #2c3e50;">💡 What You Can Do</h3>
            <div style="color: #495057;">
                {'<p><strong>Price went up</strong> - Consider these options:</p>' if is_increase else '<p><strong>Good news!</strong> Price decreased:</p>'}
                <ul style="margin: 10px 0;">
                    {'<li>Review if the service still provides good value</li><li>Check if there are alternative plans available</li><li>Consider canceling if the price is too high</li><li>Look for competitor services with better pricing</li>' if is_increase else '<li>Enjoy the savings on your subscription</li><li>Your next bill will reflect the lower price</li><li>No action needed - this is good news!</li>'}
                </ul>
            </div>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="http://localhost:5173/subscriptions/{subscription.id}"
               style="background-color: {change_color}; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 16px;">
                View Subscription Details
            </a>
        </div>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
            <p style="margin: 0; color: #666; font-size: 14px;">
                📊 Track all your subscription price changes in one place<br>
                Stay informed about your recurring costs
            </p>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #95a5a6; font-size: 12px;">
            <p>
                You're receiving this price change alert to help you manage your subscriptions.<br>
                <a href="http://localhost:5173/notifications/settings" style="color: #3498db;">Manage notification settings</a>
            </p>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
{change_icon} PRICE {change_word.upper()}

Your {subscription.provider} subscription price has changed!

Price Comparison:
- Previous Price: {subscription.currency} {old_price:.2f}
- New Price: {subscription.currency} {new_price:.2f}
- Change: {'+' if is_increase else ''}{subscription.currency} {price_diff:.2f} ({change_percent:.1f}%)
- Billing Cycle: {subscription.billing_cycle.capitalize()}

{'PRICE INCREASE - Consider:' if is_increase else 'PRICE DECREASE - Good news!'}
{'''• Review if the service still provides good value
• Check if there are alternative plans available
• Consider canceling if the price is too high
• Look for competitor services''' if is_increase else '''• Enjoy the savings on your subscription
• Your next bill will reflect the lower price
• No action needed - this is good news!'''}

View subscription: http://localhost:5173/subscriptions/{subscription.id}
Manage settings: http://localhost:5173/notifications/settings

---
Subscription Tracker - Stay informed about your recurring costs
    """

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
