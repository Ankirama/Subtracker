from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session
from app.models.push_subscription import PushSubscription
from app.config import settings
import json
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Service for sending push notifications to subscribed users."""

    def __init__(self):
        """Initialize push notification service with VAPID configuration."""
        self.vapid_private_key = settings.VAPID_PRIVATE_KEY
        self.vapid_claims = {"sub": settings.VAPID_CLAIM_EMAIL}

    async def send_notification(
        self,
        subscription: PushSubscription,
        title: str,
        body: str,
        icon: str = "/icon-192.svg",
        badge: str = "/icon-192.svg",
        tag: str = "subscription-tracker",
        data: Optional[Dict] = None,
        url: Optional[str] = None,
    ) -> bool:
        """
        Send a push notification to a single subscription.

        Args:
            subscription: PushSubscription model instance
            title: Notification title
            body: Notification body text
            icon: Icon URL (default: /icon-192.svg)
            badge: Badge icon URL (default: /icon-192.svg)
            tag: Notification tag for grouping (default: subscription-tracker)
            data: Additional data to include in notification
            url: Optional URL to open when notification is clicked

        Returns:
            True if notification sent successfully, False if subscription expired
        """
        try:
            # Prepare notification payload
            payload_data = data or {}
            if url:
                payload_data["url"] = url

            payload = json.dumps({
                "title": title,
                "body": body,
                "icon": icon,
                "badge": badge,
                "tag": tag,
                "data": payload_data,
            })

            # Prepare subscription info for pywebpush
            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                }
            }

            # Send push notification
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )

            logger.info(f"Push notification sent successfully to subscription {subscription.id}")
            return True

        except WebPushException as ex:
            logger.error(f"Push notification failed for subscription {subscription.id}: {ex}")

            # Check if subscription expired (410 Gone status)
            if ex.response and ex.response.status_code == 410:
                logger.info(f"Subscription {subscription.id} expired, marking as inactive")
                return False

            # Re-raise other exceptions
            raise

        except Exception as ex:
            logger.error(f"Unexpected error sending push notification: {ex}")
            raise

    async def send_to_user(
        self,
        db: Session,
        user_id: str,
        title: str,
        body: str,
        icon: str = "/icon-192.svg",
        badge: str = "/icon-192.svg",
        tag: str = "subscription-tracker",
        data: Optional[Dict] = None,
        url: Optional[str] = None,
    ) -> int:
        """
        Send push notification to all active subscriptions for a user.

        Args:
            db: Database session
            user_id: User ID to send notifications to
            title: Notification title
            body: Notification body text
            icon: Icon URL
            badge: Badge icon URL
            tag: Notification tag
            data: Additional notification data
            url: Optional URL to open on click

        Returns:
            Number of successfully sent notifications
        """
        # Get all active subscriptions for user
        subscriptions = db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True
        ).all()

        if not subscriptions:
            logger.info(f"No active push subscriptions found for user {user_id}")
            return 0

        success_count = 0
        for subscription in subscriptions:
            try:
                success = await self.send_notification(
                    subscription, title, body, icon, badge, tag, data, url
                )

                if success:
                    success_count += 1
                else:
                    # Mark subscription as inactive if it expired
                    subscription.is_active = False
                    db.commit()
                    logger.info(f"Marked subscription {subscription.id} as inactive")

            except Exception as e:
                logger.error(f"Error sending to subscription {subscription.id}: {e}")
                # Continue with other subscriptions

        logger.info(f"Successfully sent {success_count}/{len(subscriptions)} notifications to user {user_id}")
        return success_count


# Singleton instance
push_notification_service = PushNotificationService()
