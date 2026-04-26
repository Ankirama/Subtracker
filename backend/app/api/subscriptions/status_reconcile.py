"""Subscription status reconciliation endpoints.

Handles: POST /update-status, POST /update-renewal-status.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.subscriptions._helpers import verify_mailbox_ownership
from app.database import get_db
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.user import User
from app.security.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/update-status")
async def update_subscription_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    mailbox_id: UUID = None,
):
    """
    Manually update subscription active/inactive status based on last email confirmation.

    This runs the same logic that executes automatically after email sync:
    - Checks last_confirmed_at against billing cycle + grace period
    - Marks subscriptions as active if recently confirmed
    - Marks subscriptions as inactive if no recent confirmation

    If mailbox_id is provided, updates only that mailbox's subscriptions.
    Otherwise, updates all mailboxes for the current user.
    """
    from app.tasks.email_sync import update_subscription_statuses

    try:
        # Get mailboxes to update
        mailboxes_query = db.query(Mailbox).filter(Mailbox.user_id == current_user.id)

        if mailbox_id:
            verify_mailbox_ownership(mailbox_id, current_user.id, db)
            mailboxes_query = mailboxes_query.filter(Mailbox.id == mailbox_id)

        mailboxes = mailboxes_query.all()

        if not mailboxes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No mailboxes found"
            )

        # Update status for each mailbox
        total_activated = 0
        total_deactivated = 0
        mailbox_results = []

        for mailbox in mailboxes:
            result = update_subscription_statuses(db, mailbox.id)
            total_activated += result["activated"]
            total_deactivated += result["deactivated"]

            mailbox_results.append(
                {
                    "mailbox_id": str(mailbox.id),
                    "mailbox_email": mailbox.email_address,
                    "activated": result["activated"],
                    "deactivated": result["deactivated"],
                }
            )

        logger.info(
            f"Manual status update for user {current_user.id}: {total_activated} activated, {total_deactivated} deactivated"
        )

        return {
            "success": True,
            "total_activated": total_activated,
            "total_deactivated": total_deactivated,
            "mailboxes_updated": len(mailboxes),
            "details": mailbox_results,
            "message": f"Updated {total_activated + total_deactivated} subscription statuses",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update subscription status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription status: {str(e)}",
        )


@router.post("/update-renewal-status")
async def update_subscription_renewal_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Update renewal dates and active status for all user's subscriptions.

    Uses the RenewalCalculator service to:
    - Extract renewal dates from email content (provider-specific patterns)
    - Calculate renewal dates based on billing cycles
    - Detect inactive subscriptions (>2 billing cycles without emails)
    - Update is_active status accordingly

    Returns counts of total, activated, and deactivated subscriptions.
    """
    from app.services.renewal_calculator import (
        RenewalCalculator,
        get_subscription_emails,
    )

    # Get all user's subscriptions
    subscriptions = (
        db.query(Subscription)
        .join(Mailbox)
        .filter(Mailbox.user_id == current_user.id)
        .all()
    )

    renewal_calc = RenewalCalculator(db)

    total_processed = 0
    total_activated = 0
    total_deactivated = 0
    errors = []

    for subscription in subscriptions:
        try:
            # Get all emails for this subscription
            subscription_emails_data = get_subscription_emails(db, subscription.id)

            if not subscription_emails_data:
                logger.warning(f"No emails found for subscription {subscription.id}")
                continue

            # Extract dates and contents
            email_dates = [e["date"] for e in subscription_emails_data]
            email_contents = [
                e["body_html"] or e["body_text"] or "" for e in subscription_emails_data
            ]

            # Store old status for comparison
            old_active = subscription.is_active

            # Calculate renewal date, active status, trial status, and confirmation
            renewal_date, is_active, trial_status, is_confirmed = (
                renewal_calc.calculate_renewal_info(
                    provider=subscription.provider,
                    billing_cycle=subscription.billing_cycle,
                    email_dates=email_dates,
                    email_contents=email_contents,
                    extraction_metadata=subscription.extraction_metadata,
                )
            )

            # Update subscription
            if renewal_date:
                subscription.renewal_date = renewal_date
                logger.info(
                    f"Updated renewal date for {subscription.provider}: {renewal_date.strftime('%Y-%m-%d')}"
                )

            subscription.is_active = is_active
            subscription.trial_status = trial_status
            subscription.is_confirmed = is_confirmed

            # Track status changes
            if old_active and not is_active:
                total_deactivated += 1
                logger.info(f"Deactivated {subscription.provider}")
            elif not old_active and is_active:
                total_activated += 1
                logger.info(f"Activated {subscription.provider}")

            total_processed += 1

        except Exception as e:
            error_msg = f"Error updating {subscription.provider}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue

    db.commit()

    response = {
        "success": True,
        "total_processed": total_processed,
        "total_activated": total_activated,
        "total_deactivated": total_deactivated,
        "message": f"Updated {total_processed} subscriptions: {total_activated} activated, {total_deactivated} deactivated",
    }

    if errors:
        response["errors"] = errors

    return response
