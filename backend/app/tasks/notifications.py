"""
Celery tasks for automatic notification generation
"""

from datetime import datetime, timedelta
from sqlalchemy import or_
from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.database import get_db
from app.models.subscription import Subscription
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
)
from app.services.notification_service import NotificationService

logger = get_task_logger(__name__)


@celery_app.task(name="tasks.send_renewal_reminders")
def send_renewal_reminders():
    """
    Check for upcoming subscription renewals and send reminder notifications
    based on user preferences (days_before_renewal setting)
    """
    logger.info("Starting renewal reminder check...")
    notifications_sent = 0
    db = None

    try:
        db = next(get_db())
        # Get all active users with renewal reminder preferences
        preferences = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.notification_type
                == NotificationType.RENEWAL_REMINDER.value,
                NotificationPreference.enabled,
            )
            .all()
        )

        for pref in preferences:
            days_before = pref.days_before_renewal or 7  # Default to 7 days
            target_date = datetime.utcnow() + timedelta(days=days_before)

            # Find subscriptions renewing around the target date (±1 day tolerance)
            subscriptions = (
                db.query(Subscription)
                .filter(
                    Subscription.user_id == pref.user_id,
                    Subscription.is_active,
                    Subscription.next_billing_date.isnot(None),
                    Subscription.next_billing_date >= target_date - timedelta(days=1),
                    Subscription.next_billing_date <= target_date + timedelta(days=1),
                )
                .all()
            )

            for subscription in subscriptions:
                # Check if we already sent a notification for this renewal
                recent_cutoff = datetime.utcnow() - timedelta(days=days_before + 2)
                existing = (
                    db.query(Notification)
                    .filter(
                        Notification.user_id == pref.user_id,
                        Notification.type == NotificationType.RENEWAL_REMINDER.value,
                        Notification.related_subscription_id == subscription.id,
                        Notification.created_at >= recent_cutoff,
                    )
                    .first()
                )

                if not existing:
                    # Create renewal reminder notification
                    days_until = (
                        subscription.next_billing_date - datetime.utcnow().date()
                    ).days
                    NotificationService.create_notification(
                        db=db,
                        user_id=pref.user_id,
                        notification_type=NotificationType.RENEWAL_REMINDER,
                        priority="medium" if days_until <= 3 else "low",
                        title=f"Upcoming Renewal: {subscription.provider}",
                        message=f"Your {subscription.provider} subscription will renew in {days_until} days on {subscription.next_billing_date.strftime('%Y-%m-%d')}. Amount: {subscription.currency} {subscription.amount}",
                        related_subscription_id=subscription.id,
                        notification_metadata={
                            "days_until_renewal": days_until,
                            "amount": float(subscription.amount),
                            "currency": subscription.currency,
                            "billing_cycle": subscription.billing_cycle,
                        },
                    )
                    notifications_sent += 1
                    logger.info(
                        f"Sent renewal reminder for subscription {subscription.id} to user {pref.user_id}"
                    )

        logger.info(
            f"Renewal reminder check completed. Sent {notifications_sent} notifications"
        )
        return {"success": True, "notifications_sent": notifications_sent}

    except Exception as e:
        logger.error(f"Error in renewal reminder task: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if db is not None:
            db.close()


# DEPRECATED: This implementation is replaced by app/tasks/summary_tasks.py
# Keeping here temporarily for reference but not registered as a Celery task
# @celery_app.task(name="tasks.send_weekly_summaries")
def send_weekly_summaries_deprecated():
    """
    Send weekly subscription summaries to users who have this preference enabled
    Runs on the day of week specified in user preferences
    """
    logger.info("Starting weekly summary generation...")
    summaries_sent = 0
    db = None

    try:
        db = next(get_db())
        current_day = datetime.utcnow().weekday()  # 0 = Monday, 6 = Sunday

        # Get users who want weekly summaries on this day
        preferences = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.notification_type
                == NotificationType.WEEKLY_SUMMARY.value,
                NotificationPreference.enabled,
                or_(
                    NotificationPreference.summary_day_of_week == current_day,
                    NotificationPreference.summary_day_of_week.is_(
                        None
                    ),  # Default to Monday
                ),
            )
            .all()
        )

        for pref in preferences:
            # Get user's active subscriptions
            subscriptions = (
                db.query(Subscription)
                .filter(
                    Subscription.user_id == pref.user_id, Subscription.is_active
                )
                .all()
            )

            if not subscriptions:
                continue

            # Calculate weekly stats
            total_monthly_cost = sum(
                _convert_to_monthly(sub.amount, sub.billing_cycle)
                for sub in subscriptions
            )

            # Get subscriptions renewing in the next 7 days
            upcoming_renewals = [
                sub
                for sub in subscriptions
                if sub.next_billing_date
                and (sub.next_billing_date - datetime.utcnow().date()).days <= 7
            ]

            # Build summary message
            message_parts = [
                f"You have {len(subscriptions)} active subscription{'s' if len(subscriptions) != 1 else ''}.",
                f"Total monthly cost: ${total_monthly_cost:.2f}",
            ]

            if upcoming_renewals:
                message_parts.append(
                    f"{len(upcoming_renewals)} subscription{'s' if len(upcoming_renewals) != 1 else ''} "
                    f"renewing in the next 7 days."
                )

            # Create weekly summary notification
            NotificationService.create_notification(
                db=db,
                user_id=pref.user_id,
                notification_type=NotificationType.WEEKLY_SUMMARY,
                priority="low",
                title="Weekly Subscription Summary",
                message=" ".join(message_parts),
                notification_metadata={
                    "total_subscriptions": len(subscriptions),
                    "total_monthly_cost": float(total_monthly_cost),
                    "upcoming_renewals_count": len(upcoming_renewals),
                    "upcoming_renewals": [
                        {
                            "name": sub.name,
                            "next_billing_date": sub.next_billing_date.isoformat(),
                            "amount": float(sub.amount),
                        }
                        for sub in upcoming_renewals
                    ],
                },
            )
            summaries_sent += 1
            logger.info(f"Sent weekly summary to user {pref.user_id}")

        logger.info(
            f"Weekly summary generation completed. Sent {summaries_sent} summaries"
        )
        return {"success": True, "summaries_sent": summaries_sent}

    except Exception as e:
        logger.error(f"Error in weekly summary task: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if db is not None:
            db.close()


# DEPRECATED: This implementation is replaced by app/tasks/summary_tasks.py
# Keeping here temporarily for reference but not registered as a Celery task
# @celery_app.task(name="tasks.send_monthly_summaries")
def send_monthly_summaries_deprecated():
    """
    Send monthly subscription summaries to users who have this preference enabled
    Runs on the day of month specified in user preferences
    """
    logger.info("Starting monthly summary generation...")
    summaries_sent = 0
    db = None

    try:
        db = next(get_db())
        current_day = datetime.utcnow().day

        # Get users who want monthly summaries on this day (or default to 1st)
        preferences = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.notification_type
                == NotificationType.MONTHLY_SUMMARY.value,
                NotificationPreference.enabled,
                or_(
                    NotificationPreference.summary_day_of_month == current_day,
                    NotificationPreference.summary_day_of_month.is_(
                        None
                    ),  # Default to 1st
                ),
            )
            .all()
        )

        for pref in preferences:
            # Get user's active subscriptions
            subscriptions = (
                db.query(Subscription)
                .filter(
                    Subscription.user_id == pref.user_id, Subscription.is_active
                )
                .all()
            )

            if not subscriptions:
                continue

            # Calculate monthly stats
            total_monthly_cost = sum(
                _convert_to_monthly(sub.amount, sub.billing_cycle)
                for sub in subscriptions
            )

            yearly_projection = total_monthly_cost * 12

            # Get subscriptions renewing in the next 30 days
            upcoming_renewals = [
                sub
                for sub in subscriptions
                if sub.next_billing_date
                and (sub.next_billing_date - datetime.utcnow().date()).days <= 30
            ]

            # Group by billing cycle
            cycle_counts = {}
            for sub in subscriptions:
                cycle = sub.billing_cycle or "unknown"
                cycle_counts[cycle] = cycle_counts.get(cycle, 0) + 1

            # Build summary message
            message_parts = [
                "Monthly subscription report:",
                f"• {len(subscriptions)} active subscription{'s' if len(subscriptions) != 1 else ''}",
                f"• ${total_monthly_cost:.2f}/month (${yearly_projection:.2f}/year projected)",
                f"• {len(upcoming_renewals)} renewal{'s' if len(upcoming_renewals) != 1 else ''} this month",
            ]

            # Create monthly summary notification
            NotificationService.create_notification(
                db=db,
                user_id=pref.user_id,
                notification_type=NotificationType.MONTHLY_SUMMARY,
                priority="low",
                title="Monthly Subscription Report",
                message="\n".join(message_parts),
                notification_metadata={
                    "total_subscriptions": len(subscriptions),
                    "total_monthly_cost": float(total_monthly_cost),
                    "yearly_projection": float(yearly_projection),
                    "upcoming_renewals_count": len(upcoming_renewals),
                    "billing_cycle_breakdown": cycle_counts,
                },
            )
            summaries_sent += 1
            logger.info(f"Sent monthly summary to user {pref.user_id}")

        logger.info(
            f"Monthly summary generation completed. Sent {summaries_sent} summaries"
        )
        return {"success": True, "summaries_sent": summaries_sent}

    except Exception as e:
        logger.error(f"Error in monthly summary task: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if db is not None:
            db.close()


@celery_app.task(name="tasks.check_inactive_subscriptions")
def check_inactive_subscriptions():
    """
    Check for subscriptions that haven't had any activity (emails) in a long time
    and notify users about potentially inactive or cancelled subscriptions
    """
    logger.info("Starting inactive subscription check...")
    notifications_sent = 0
    db = None

    try:
        db = next(get_db())
        # Get users who have inactive subscription notifications enabled
        preferences = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.notification_type
                == NotificationType.INACTIVE_SUBSCRIPTION.value,
                NotificationPreference.enabled,
            )
            .all()
        )

        for pref in preferences:
            # Find subscriptions with no recent activity (no emails in 90+ days)
            inactive_threshold = datetime.utcnow() - timedelta(days=90)

            subscriptions = (
                db.query(Subscription)
                .filter(
                    Subscription.user_id == pref.user_id,
                    Subscription.is_active,
                    or_(
                        Subscription.last_confirmed_at < inactive_threshold,
                        Subscription.last_confirmed_at.is_(None),
                    ),
                )
                .all()
            )

            for subscription in subscriptions:
                # Check if we already sent a notification for this subscription
                recent_cutoff = datetime.utcnow() - timedelta(days=30)
                existing = (
                    db.query(Notification)
                    .filter(
                        Notification.user_id == pref.user_id,
                        Notification.type
                        == NotificationType.INACTIVE_SUBSCRIPTION.value,
                        Notification.related_subscription_id == subscription.id,
                        Notification.created_at >= recent_cutoff,
                    )
                    .first()
                )

                if not existing:
                    days_inactive = (
                        (datetime.utcnow() - subscription.last_confirmed_at).days
                        if subscription.last_confirmed_at
                        else None
                    )

                    message = f"No activity detected for {subscription.provider}"
                    if days_inactive:
                        message += f" in the last {days_inactive} days"
                    message += (
                        ". You may want to verify if this subscription is still active."
                    )

                    # Create inactive subscription notification
                    NotificationService.create_notification(
                        db=db,
                        user_id=pref.user_id,
                        notification_type=NotificationType.INACTIVE_SUBSCRIPTION,
                        priority="low",
                        title=f"Inactive Subscription: {subscription.provider}",
                        message=message,
                        related_subscription_id=subscription.id,
                        notification_metadata={
                            "days_inactive": days_inactive,
                            "last_confirmed_at": (
                                subscription.last_confirmed_at.isoformat()
                                if subscription.last_confirmed_at
                                else None
                            ),
                        },
                    )
                    notifications_sent += 1
                    logger.info(
                        f"Sent inactive notification for subscription {subscription.id} to user {pref.user_id}"
                    )

        logger.info(
            f"Inactive subscription check completed. Sent {notifications_sent} notifications"
        )
        return {"success": True, "notifications_sent": notifications_sent}

    except Exception as e:
        logger.error(f"Error in inactive subscription task: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if db is not None:
            db.close()


def _convert_to_monthly(amount: float, billing_cycle: str) -> float:
    """
    Convert subscription amount to monthly equivalent
    """
    if not amount:
        return 0.0

    cycle_multipliers = {
        "weekly": 52 / 12,
        "monthly": 1,
        "quarterly": 1 / 3,
        "semi-annually": 1 / 6,
        "annually": 1 / 12,
        "yearly": 1 / 12,
        "biweekly": 26 / 12,
    }

    multiplier = cycle_multipliers.get(
        billing_cycle.lower() if billing_cycle else "monthly", 1
    )
    return amount * multiplier
