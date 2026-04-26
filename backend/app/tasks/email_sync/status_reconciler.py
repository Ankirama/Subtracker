"""Subscription activity reconciliation.

Provides ``update_subscription_statuses`` which scans every subscription
under a mailbox and flips ``is_active`` based on the time elapsed since
``last_confirmed_at`` plus a billing-cycle-specific grace period.

Called both from the post-sync hook in ``celery_tasks.sync_mailbox_emails``
and from the public endpoint ``api/subscriptions/status_reconcile.py``.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


def update_subscription_statuses(db: Session, mailbox_id: UUID) -> Dict[str, int]:
    """
    Update subscription active status based on last email confirmation.

    Logic:
    - If last email was received within expected billing cycle + grace period, mark as active
    - Otherwise, mark as inactive

    Grace periods by billing cycle:
    - weekly: 2 weeks (14 days)
    - monthly: 2 months (60 days)
    - quarterly: 4 months (120 days)
    - biannual: 7 months (210 days)
    - yearly/annual: 13 months (395 days)

    Returns:
        Dict with counts of activated and deactivated subscriptions
    """
    # Define grace periods for each billing cycle (in days)
    GRACE_PERIODS = {
        "weekly": 14,
        "monthly": 60,
        "quarterly": 120,
        "biannual": 210,
        "yearly": 395,
        "annual": 395,
    }

    now = datetime.now(timezone.utc)
    activated_count = 0
    deactivated_count = 0

    # Get all subscriptions for this mailbox
    subscriptions = (
        db.query(Subscription).filter(Subscription.mailbox_id == mailbox_id).all()
    )

    for sub in subscriptions:
        if not sub.billing_cycle:
            # Skip subscriptions without billing cycle defined
            continue

        if sub.manual_status_override:
            # Skip subscriptions with manual status override - user has manually set the status
            continue

        # Get grace period for this billing cycle (default to 60 days if unknown)
        billing_cycle_lower = sub.billing_cycle.lower()
        grace_days = GRACE_PERIODS.get(billing_cycle_lower, 60)

        # Calculate cutoff date
        cutoff_date = now - timedelta(days=grace_days)

        # Normalize timezone before comparison (SQLite returns timezone-naive datetimes)
        last_confirmed = sub.last_confirmed_at
        if last_confirmed.tzinfo is None:
            last_confirmed = last_confirmed.replace(tzinfo=timezone.utc)

        # Check if subscription should be active
        should_be_active = last_confirmed >= cutoff_date

        # Update status if it changed
        if should_be_active and not sub.is_active:
            sub.is_active = True
            activated_count += 1
            logger.info(
                f"Activated subscription: {sub.provider} (last confirmed: {last_confirmed})"
            )
        elif not should_be_active and sub.is_active:
            sub.is_active = False
            deactivated_count += 1
            logger.info(
                f"Deactivated subscription: {sub.provider} (last confirmed: {last_confirmed}, cutoff: {cutoff_date})"
            )

    if activated_count > 0 or deactivated_count > 0:
        db.commit()
        logger.info(
            f"Subscription status update: {activated_count} activated, {deactivated_count} deactivated"
        )

    return {"activated": activated_count, "deactivated": deactivated_count}
