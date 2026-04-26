"""
Notification service for creating and delivering notifications.

Handles both in-app and email notifications.
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
    NotificationPriority,
)
from app.models.user import User
from app.models.subscription import Subscription
from app.services.email.templates import EmailTemplates
from app.services.email.transport import EmailService

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications."""

    @staticmethod
    def create_notification(
        db: Session,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        related_subscription_id: Optional[UUID] = None,
        notification_metadata: Optional[dict] = None,
    ) -> Notification:
        """
        Create a new notification.

        This creates the notification in the database and will be picked up
        by the delivery service to send via appropriate channels.
        """
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            related_subscription_id=related_subscription_id,
            notification_metadata=notification_metadata,
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        logger.info(f"Created notification: {notification.id} for user {user_id}")

        # Schedule email delivery if user has email enabled for this type
        NotificationService._schedule_email_delivery(db, notification)

        return notification

    @staticmethod
    def _schedule_email_delivery(db: Session, notification: Notification):
        """
        Schedule email delivery for a notification if user preferences allow.

        This checks user preferences and delivers email immediately.
        """
        # Get user preferences
        preference = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.user_id == notification.user_id,
                NotificationPreference.notification_type == notification.type,
            )
            .first()
        )

        # If no preference exists, use defaults (enabled)
        email_enabled = preference.email_enabled if preference else True
        enabled = preference.enabled if preference else True

        if not (enabled and email_enabled):
            logger.info(
                f"Email delivery skipped for notification {notification.id} (disabled in preferences)"
            )
            return

        # Get user email
        user = db.query(User).filter(User.id == notification.user_id).first()
        if not user or not user.email:
            logger.warning(
                f"Cannot send email for notification {notification.id}: user email not found"
            )
            return

        # Send email based on notification type
        success = False
        error_message = None

        try:
            if notification.type == NotificationType.RENEWAL_REMINDER:
                # Get subscription details
                if notification.related_subscription_id:
                    subscription = (
                        db.query(Subscription)
                        .filter(Subscription.id == notification.related_subscription_id)
                        .first()
                    )

                    if subscription:
                        metadata = notification.notification_metadata or {}
                        days_until_renewal = metadata.get("days_until_renewal", 0)
                        user_name = user.name or "there"
                        subject = (
                            f"Reminder: {subscription.name} renews in "
                            f"{days_until_renewal} days"
                        )
                        html_content = EmailTemplates.generate_renewal_reminder(
                            user_name=user_name,
                            subscription_name=subscription.name,
                            renewal_date=subscription.next_billing_date,
                            amount=subscription.amount,
                            currency=subscription.currency,
                            days_until_renewal=days_until_renewal,
                        )
                        plain_content = f"""
Hi {user_name},

This is a reminder that your {subscription.name} subscription will renew in {days_until_renewal} days.

Renewal Date: {subscription.next_billing_date.strftime('%B %d, %Y')}
Amount: {subscription.currency} {subscription.amount:.2f}

If you wish to cancel or modify this subscription, please log in to your Subscription Tracker account.

Best regards,
Subscription Tracker Team
        """.strip()
                        success, error_message = EmailService(db).send_email(
                            to_email=user.email,
                            subject=subject,
                            html_content=html_content,
                            plain_content=plain_content,
                        )

            elif notification.type in [
                NotificationType.WEEKLY_SUMMARY,
                NotificationType.MONTHLY_SUMMARY,
            ]:
                # For summaries, metadata should contain the summary data
                metadata = notification.notification_metadata or {}

                if notification.type == NotificationType.WEEKLY_SUMMARY:
                    user_name = user.name or "there"
                    total_spent = metadata.get("total_spent", 0.0)
                    currency = metadata.get("currency", "USD")
                    subscriptions = metadata.get("subscriptions", [])
                    upcoming_renewals = metadata.get("upcoming_renewals", [])
                    subject = (
                        f"Your Weekly Subscription Summary - "
                        f"{currency} {total_spent:.2f}"
                    )
                    html_content = EmailTemplates.generate_weekly_summary(
                        user_name=user_name,
                        total_spent=total_spent,
                        currency=currency,
                        subscriptions=subscriptions,
                        upcoming_renewals=upcoming_renewals,
                    )
                    plain_content = f"""
Hi {user_name},

Here's your weekly subscription summary.

Total Spent This Week: {currency} {total_spent:.2f}

Active Subscriptions: {len(subscriptions)}

Upcoming Renewals: {len(upcoming_renewals)}

Log in to your Subscription Tracker account to view more details.

Best regards,
Subscription Tracker Team
        """.strip()
                    success, error_message = EmailService(db).send_email(
                        to_email=user.email,
                        subject=subject,
                        html_content=html_content,
                        plain_content=plain_content,
                    )
                else:  # MONTHLY_SUMMARY
                    user_name = user.name or "there"
                    total_spent = metadata.get("total_spent", 0.0)
                    currency = metadata.get("currency", "USD")
                    subscriptions = metadata.get("subscriptions", [])
                    spending_breakdown = metadata.get("spending_breakdown", {})
                    comparison_last_month = metadata.get("comparison_last_month")
                    subject = (
                        f"Your Monthly Subscription Summary - "
                        f"{currency} {total_spent:.2f}"
                    )
                    html_content = EmailTemplates.generate_monthly_summary(
                        user_name=user_name,
                        total_spent=total_spent,
                        currency=currency,
                        subscriptions=subscriptions,
                        spending_breakdown=spending_breakdown,
                        comparison_last_month=comparison_last_month,
                    )
                    plain_content = f"""
Hi {user_name},

Here's your monthly subscription summary.

Total Spent This Month: {currency} {total_spent:.2f}

Active Subscriptions: {len(subscriptions)}

Log in to your Subscription Tracker account to view detailed analytics.

Best regards,
Subscription Tracker Team
        """.strip()
                    success, error_message = EmailService(db).send_email(
                        to_email=user.email,
                        subject=subject,
                        html_content=html_content,
                        plain_content=plain_content,
                    )

            # Update notification with email delivery status
            if success:
                notification.email_sent = True
                notification.email_sent_at = datetime.now()
                logger.info(
                    f"Email sent successfully for notification {notification.id}"
                )
            else:
                notification.email_error = error_message
                logger.error(
                    f"Failed to send email for notification {notification.id}: {error_message}"
                )

            db.commit()

        except Exception as e:
            error_message = str(e)
            notification.email_error = error_message
            db.commit()
            logger.error(
                f"Exception sending email for notification {notification.id}: {error_message}"
            )

    @staticmethod
    def mark_as_read(db: Session, user_id: UUID, notification_ids: List[UUID]) -> int:
        """
        Mark notifications as read.

        Returns the number of notifications marked as read.
        """
        updated_count = (
            db.query(Notification)
            .filter(
                Notification.id.in_(notification_ids),
                Notification.user_id == user_id,
                not Notification.is_read,
            )
            .update(
                {"is_read": True, "read_at": datetime.now()}, synchronize_session=False
            )
        )

        db.commit()

        logger.info(f"Marked {updated_count} notifications as read for user {user_id}")
        return updated_count

    @staticmethod
    def mark_all_as_read(db: Session, user_id: UUID) -> int:
        """
        Mark all unread notifications as read for a user.

        Returns the number of notifications marked as read.
        """
        updated_count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, not Notification.is_read)
            .update(
                {"is_read": True, "read_at": datetime.now()}, synchronize_session=False
            )
        )

        db.commit()

        logger.info(
            f"Marked all {updated_count} notifications as read for user {user_id}"
        )
        return updated_count

    @staticmethod
    def get_unread_count(db: Session, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id, not Notification.is_read)
            .count()
        )

    @staticmethod
    def delete_notification(db: Session, user_id: UUID, notification_id: UUID) -> bool:
        """
        Delete a notification.

        Returns True if deleted, False if not found.
        """
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )

        if notification:
            db.delete(notification)
            db.commit()
            logger.info(f"Deleted notification {notification_id}")
            return True

        return False

    @staticmethod
    def get_or_create_preference(
        db: Session, user_id: UUID, notification_type: NotificationType
    ) -> NotificationPreference:
        """
        Get or create a notification preference for a user.

        If preference doesn't exist, creates one with default values.
        """
        preference = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
            .first()
        )

        if not preference:
            # Create with defaults
            preference = NotificationPreference(
                user_id=user_id,
                notification_type=notification_type,
                enabled=True,
                in_app_enabled=True,
                email_enabled=True,
                days_before_renewal=(
                    3
                    if notification_type == NotificationType.RENEWAL_REMINDER
                    else None
                ),
                summary_day_of_week=(
                    0 if notification_type == NotificationType.WEEKLY_SUMMARY else None
                ),
                summary_day_of_month=(
                    1 if notification_type == NotificationType.MONTHLY_SUMMARY else None
                ),
            )
            db.add(preference)
            db.commit()
            db.refresh(preference)
            logger.info(
                f"Created default preference for user {user_id}, type {notification_type}"
            )

        return preference

    @staticmethod
    def init_user_preferences(db: Session, user_id: UUID):
        """
        Initialize all notification preferences for a new user.

        Creates preferences for all notification types with default values.
        """
        notification_types = [
            NotificationType.RENEWAL_REMINDER,
            NotificationType.WEEKLY_SUMMARY,
            NotificationType.MONTHLY_SUMMARY,
            NotificationType.INACTIVE_SUBSCRIPTION,
            NotificationType.PRICE_CHANGE,
            NotificationType.SYSTEM_ANNOUNCEMENT,
        ]

        for notification_type in notification_types:
            NotificationService.get_or_create_preference(db, user_id, notification_type)

        logger.info(f"Initialized notification preferences for user {user_id}")
