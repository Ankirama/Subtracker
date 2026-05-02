"""
Celery task for monitoring budgets and sending alerts.

Checks budgets daily and sends notifications when they approach or exceed limits.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.budget import Budget
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.user import User
from app.services.budget_service import BudgetService
from app.services.email.templates.budget_alert import generate_budget_alert_email
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


def should_send_budget_alert(budget_id: str, alert_type: str, db: Session) -> bool:
    """
    Check if we should send a budget alert.

    Args:
        budget_id: ID of the budget
        alert_type: Type of alert (warning or exceeded)
        db: Database session

    Returns:
        True if alert should be sent
    """
    # Check if we already sent an alert for this budget in the last 24 hours
    recent_alert = (
        db.query(Notification)
        .filter(
            Notification.related_budget_id == budget_id,
            Notification.type == NotificationType.BUDGET_ALERT,
            Notification.created_at >= datetime.now() - timedelta(hours=24),
        )
        .first()
    )

    if recent_alert:
        # Check if status changed (e.g., from warning to exceeded)
        if (
            recent_alert.notification_metadata
            and recent_alert.notification_metadata.get("alert_type") == alert_type
        ):
            logger.debug(
                f"Already sent {alert_type} alert for budget {budget_id} in last 24h"
            )
            return False

    return True


def create_budget_notification(
    budget: Budget, alert_type: str, message: str, db: Session
) -> Notification:
    """
    Create a budget alert notification.

    Args:
        budget: The budget that triggered the alert
        alert_type: Type of alert (warning or exceeded)
        message: Alert message
        db: Database session

    Returns:
        Created notification
    """
    priority = (
        NotificationPriority.MEDIUM
        if alert_type == "warning"
        else NotificationPriority.HIGH
    )

    notification = Notification(
        user_id=budget.user_id,
        type=NotificationType.BUDGET_ALERT,
        priority=priority,
        title=f"Budget Alert: {budget.name}",
        message=message,
        related_budget_id=str(budget.id),
        notification_metadata={
            "alert_type": alert_type,
            "budget_id": str(budget.id),
            "budget_name": budget.name,
            "category": budget.category,
        },
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    logger.info(
        f"Created budget alert notification for budget {budget.id}: {alert_type}"
    )
    return notification


async def send_budget_alert_email(
    budget: Budget, alert_type: str, message: str, user: User
):
    """
    Send budget alert email to user.

    Args:
        budget: The budget that triggered the alert
        alert_type: Type of alert (warning or exceeded)
        message: Alert message
        user: User to send email to
    """
    subject = f"Budget Alert: {budget.name}"

    # Get budget status for details
    db = SessionLocal()
    try:
        budget_status = BudgetService.get_budget_status(db, budget)

        html_content, plain_content = generate_budget_alert_email(
            budget_name=budget.name,
            budget_category=budget.category,
            alert_type=alert_type,
            message=message,
            currency=budget_status.currency,
            current_spending=budget_status.current_spending,
            limit_amount=budget_status.limit_amount,
            remaining=budget_status.remaining,
            percentage_used=budget_status.percentage_used,
            period_start=budget_status.period_start,
            period_end=budget_status.period_end,
        )

        await EmailService.send_email(
            to_email=user.email,
            subject=subject,
            html_content=html_content,
            plain_content=plain_content,
        )

        logger.info(f"Sent budget alert email to {user.email} for budget {budget.id}")

    finally:
        db.close()


@celery_app.task(name="app.tasks.budget_alerts.check_budget_alerts")
def check_budget_alerts():
    """
    Check all budgets and send alerts for those approaching or exceeding limits.

    This task should be run daily via Celery Beat.
    """
    db = SessionLocal()
    try:
        logger.info("Starting budget alerts check")

        # Get all budgets with alerts enabled
        budgets = db.query(Budget).filter(Budget.alert_enabled == "true").all()

        total_alerts = 0
        total_emails = 0

        for budget in budgets:
            try:
                # Get budget status
                status = BudgetService.get_budget_status(db, budget)

                # Determine if alert should be sent
                alert_type = None
                message = None

                if status.status == "exceeded":
                    alert_type = "exceeded"
                    message = f"Your budget '{budget.name}' has exceeded its limit! You've spent {status.currency} {status.current_spending:.2f} of {status.currency} {status.limit_amount:.2f} ({status.percentage_used:.1f}%)."

                elif status.status == "warning":
                    alert_type = "warning"
                    message = f"Your budget '{budget.name}' is approaching its limit. You've spent {status.currency} {status.current_spending:.2f} of {status.currency} {status.limit_amount:.2f} ({status.percentage_used:.1f}%)."

                # Send alert if needed
                if alert_type and message:
                    if should_send_budget_alert(str(budget.id), alert_type, db):
                        # Create in-app notification
                        create_budget_notification(budget, alert_type, message, db)
                        total_alerts += 1

                        # Send email if user has email notifications enabled
                        user = db.query(User).filter(User.id == budget.user_id).first()
                        if user and user.settings.get("notifications", {}).get(
                            "email_enabled", True
                        ):
                            # Run async function synchronously in Celery task
                            import asyncio

                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(
                                send_budget_alert_email(
                                    budget, alert_type, message, user
                                )
                            )
                            loop.close()
                            total_emails += 1

            except Exception as e:
                logger.error(
                    f"Error processing budget {budget.id}: {str(e)}", exc_info=True
                )
                continue

        logger.info(
            f"Budget alerts check complete. Created {total_alerts} notifications, sent {total_emails} emails."
        )
        return {
            "total_budgets_checked": len(budgets),
            "alerts_created": total_alerts,
            "emails_sent": total_emails,
        }

    except Exception as e:
        logger.error(f"Error in budget alerts check: {str(e)}", exc_info=True)
        raise

    finally:
        db.close()
