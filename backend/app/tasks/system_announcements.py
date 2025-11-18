"""
Celery task for broadcasting system announcements.

Sends system-wide announcements to all users or specific user groups.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from decimal import Decimal
import logging
import uuid

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.notification import Notification, NotificationPreference, NotificationType, NotificationPriority
from app.models.user import User
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


def create_announcement_notification(
    user_id: uuid.UUID,
    title: str,
    message: str,
    priority: str,
    db: Session
) -> Notification:
    """
    Create a system announcement notification for a user.

    Args:
        user_id: User to notify
        title: Announcement title
        message: Announcement message
        priority: Notification priority
        db: Database session

    Returns:
        Created notification
    """
    # Map string priority to enum
    priority_map = {
        "low": NotificationPriority.LOW,
        "medium": NotificationPriority.MEDIUM,
        "high": NotificationPriority.HIGH
    }

    notification = Notification(
        user_id=user_id,
        type=NotificationType.SYSTEM_ANNOUNCEMENT,
        priority=priority_map.get(priority, NotificationPriority.MEDIUM),
        title=f"📢 {title}",
        message=message,
        notification_metadata={
            "announcement_priority": priority,
            "broadcast_time": datetime.now().isoformat()
        }
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(f"Created system announcement notification for user {user_id}")
    return notification


async def send_announcement_email(
    notification: Notification,
    user: User,
    db: Session
) -> tuple[bool, Optional[str]]:
    """
    Send system announcement email.

    Args:
        notification: The notification
        user: User to send to
        db: Database session

    Returns:
        (success, error_message)
    """
    metadata = notification.notification_metadata
    priority = metadata.get('announcement_priority', 'medium')

    # Styling based on priority
    if priority == 'high':
        banner_color = "#e53e3e"
        banner_bg = "#fed7d7"
        banner_border = "#fc8181"
        priority_badge = "🔴 HIGH PRIORITY"
    elif priority == 'low':
        banner_color = "#3182ce"
        banner_bg = "#bee3f8"
        banner_border = "#90cdf4"
        priority_badge = "🔵 INFORMATION"
    else:  # medium
        banner_color = "#d69e2e"
        banner_bg = "#fef5e7"
        banner_border = "#f6e05e"
        priority_badge = "🟡 ANNOUNCEMENT"

    # Extract title (remove emoji prefix)
    title = notification.title.replace("📢 ", "")

    # Build email content
    subject = f"📢 System Announcement: {title}"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Priority Banner -->
        <div style="background-color: {banner_bg}; border: 2px solid {banner_border}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 24px; color: {banner_color};">
                📢 SYSTEM ANNOUNCEMENT
            </h1>
            <p style="margin: 10px 0 0 0; font-size: 14px; color: {banner_color}; font-weight: bold;">
                {priority_badge}
            </p>
        </div>

        <!-- Announcement Content -->
        <div style="background-color: #fff; border: 2px solid {banner_color}; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">{title}</h2>
            <div style="font-size: 16px; color: #34495e; line-height: 1.6;">
                {notification.message.replace(chr(10), '<br>')}
            </div>
        </div>

        <!-- Action Button -->
        <div style="text-align: center; margin: 30px 0;">
            <a href="http://localhost:5173/notifications"
               style="background-color: {banner_color}; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 16px;">
                View All Notifications
            </a>
        </div>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
            <p style="margin: 0; color: #666; font-size: 14px;">
                📬 Stay informed about important updates and announcements<br>
                Manage your notification preferences in settings
            </p>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #95a5a6; font-size: 12px;">
            <p>
                You're receiving this system announcement as a Subscription Tracker user.<br>
                <a href="http://localhost:5173/notifications/settings" style="color: #3498db;">Manage notification settings</a>
            </p>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
📢 SYSTEM ANNOUNCEMENT
{priority_badge}

{title}

{notification.message}

View all notifications: http://localhost:5173/notifications
Manage settings: http://localhost:5173/notifications/settings

---
Subscription Tracker - System Announcements
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
        logger.info(f"Sent system announcement email to {user.email}")
    else:
        logger.error(f"Failed to send system announcement email to {user.email}: {error}")

    return success, error


@celery_app.task(name="tasks.broadcast_system_announcement")
def broadcast_system_announcement(
    announcement_id: str,
    title: str,
    message: str,
    priority: str = "medium",
    target_all_users: bool = True,
    target_user_ids: Optional[List[str]] = None
):
    """
    Broadcast a system announcement to users.

    This task:
    1. Identifies target users (all or specific)
    2. Checks user notification preferences
    3. Creates in-app notifications
    4. Sends email notifications based on preferences

    Args:
        announcement_id: Unique announcement ID
        title: Announcement title
        message: Announcement message
        priority: Priority level ('low', 'medium', 'high')
        target_all_users: Whether to send to all users
        target_user_ids: List of specific user IDs to target (if not all users)

    Returns:
        Task result with statistics
    """
    db = SessionLocal()
    try:
        logger.info(f"Broadcasting system announcement '{title}' (ID: {announcement_id})")

        # Determine target users
        if target_all_users:
            users = db.query(User).filter(User.is_active == True).all()
            logger.info(f"Broadcasting to all {len(users)} active users")
        else:
            if not target_user_ids:
                logger.warning("No target users specified and target_all_users=False")
                return {
                    "status": "error",
                    "error": "No target users specified"
                }

            # Convert string UUIDs to UUID objects
            user_uuids = [uuid.UUID(uid) for uid in target_user_ids]
            users = db.query(User).filter(
                User.id.in_(user_uuids),
                User.is_active == True
            ).all()
            logger.info(f"Broadcasting to {len(users)} specified users")

        total_notifications = 0
        total_emails = 0

        for user in users:
            # Check user preferences
            pref = db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user.id,
                NotificationPreference.notification_type == NotificationType.SYSTEM_ANNOUNCEMENT,
                NotificationPreference.enabled == True
            ).first()

            # Default to enabled if no preference exists
            if pref is None or pref.enabled:
                # Create notification
                notification = create_announcement_notification(
                    user_id=user.id,
                    title=title,
                    message=message,
                    priority=priority,
                    db=db
                )
                total_notifications += 1

                # Send email if enabled
                email_enabled = pref.email_enabled if pref else True
                if email_enabled:
                    # Run async function synchronously in Celery task
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    success, _ = loop.run_until_complete(
                        send_announcement_email(notification, user, db)
                    )
                    loop.close()

                    if success:
                        total_emails += 1

        logger.info(f"Announcement broadcast complete: {total_notifications} notifications created, {total_emails} emails sent")
        return {
            "status": "success",
            "announcement_id": announcement_id,
            "notifications_created": total_notifications,
            "emails_sent": total_emails
        }

    except Exception as e:
        logger.error(f"Error broadcasting system announcement: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()
