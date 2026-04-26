"""Subscription merge & split endpoints.

Handles: POST /{subscription_id}/merge/{target_id}, POST /{subscription_id}/split.
"""

import logging
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.email_message import subscription_emails
from app.models.mailbox import Mailbox
from app.models.price_history import PriceHistory
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import SubscriptionResponse
from app.security.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{subscription_id}/merge/{target_id}")
async def merge_subscriptions(
    subscription_id: UUID,
    target_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Merge two subscriptions together, keeping the target and removing the source.

    - Transfers all email links from source to target
    - Creates price history if amounts differ
    - Updates target with latest information
    - Deletes source subscription
    """
    # Get both subscriptions
    source_sub = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id, Subscription.user_id == current_user.id
        )
        .first()
    )

    target_sub = (
        db.query(Subscription)
        .filter(Subscription.id == target_id, Subscription.user_id == current_user.id)
        .first()
    )

    if not source_sub or not target_sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both subscriptions not found",
        )

    if source_sub.id == target_sub.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot merge subscription with itself",
        )

    # Determine which is older (keep the older created_at)
    if source_sub.created_at < target_sub.created_at:
        # Source is older, swap them
        source_sub, target_sub = target_sub, source_sub

    try:
        # Check if amounts differ (create price history)
        if (
            source_sub.amount
            and target_sub.amount
            and source_sub.amount != target_sub.amount
        ):
            change_percentage = (
                (float(target_sub.amount) - float(source_sub.amount))
                / float(source_sub.amount)
            ) * 100
            change_type = (
                "increase"
                if float(target_sub.amount) > float(source_sub.amount)
                else "decrease"
            )

            price_history_record = PriceHistory(
                subscription_id=target_sub.id,
                old_amount=source_sub.amount,
                new_amount=target_sub.amount,
                currency=target_sub.currency or source_sub.currency,
                change_type=change_type,
                change_percentage=round(change_percentage, 2),
                detected_from="manual_merge",
                notes=f"Merged duplicate subscription - price changed from {source_sub.amount} to {target_sub.amount}",
            )
            db.add(price_history_record)

        # Update target with newer information from source
        target_sub.amount = target_sub.amount or source_sub.amount
        target_sub.currency = target_sub.currency or source_sub.currency
        target_sub.billing_cycle = target_sub.billing_cycle or source_sub.billing_cycle
        target_sub.renewal_date = target_sub.renewal_date or source_sub.renewal_date
        target_sub.custom_label = target_sub.custom_label or source_sub.custom_label
        target_sub.updated_at = datetime.now()

        # Transfer all email links from source to target
        db.execute(
            subscription_emails.update()
            .where(subscription_emails.c.subscription_id == source_sub.id)
            .values(subscription_id=target_sub.id)
        )

        # Transfer all price history records from source to target
        db.execute(
            PriceHistory.__table__.update()
            .where(PriceHistory.subscription_id == source_sub.id)
            .values(subscription_id=target_sub.id)
        )

        # Delete source subscription
        db.delete(source_sub)
        db.commit()

        logger.info(
            f"Merged subscription {source_sub.id} into {target_sub.id} for provider {target_sub.provider}"
        )

        return {
            "success": True,
            "message": f"Successfully merged {source_sub.provider} subscriptions",
            "target_subscription_id": str(target_sub.id),
            "deleted_subscription_id": str(source_sub.id),
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error merging subscriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to merge subscriptions: {str(e)}",
        )


@router.post("/{subscription_id}/split")
async def split_subscription(
    subscription_id: UUID,
    email_groups: List[dict],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually split a subscription into multiple subscriptions based on email grouping.

    This allows users to separate merged subscriptions that should be distinct services.
    For example, splitting 3 different OVH services that were incorrectly merged into one.

    Args:
        subscription_id: The subscription to split
        email_groups: List of groups, each containing:
            - email_ids: List of email IDs for this group
            - custom_label: Optional label for the new subscription
            - amount: Optional amount override
            - service_references: Optional service references (e.g., service_code)

    Returns:
        List of newly created subscriptions

    Example request body:
    [
        {
            "email_ids": ["email-uuid-1", "email-uuid-2"],
            "custom_label": "OVH VPS FR73880615",
            "amount": 23.99,
            "service_references": {"service_code": "FR73880615"}
        },
        {
            "email_ids": ["email-uuid-3", "email-uuid-4"],
            "custom_label": "OVH Domain FR69204676",
            "amount": 17.47,
            "service_references": {"service_code": "FR69204676"}
        }
    ]
    """
    # Get original subscription and verify ownership
    original_sub = (
        db.query(Subscription)
        .join(Mailbox)
        .options(joinedload(Subscription.source_emails))
        .filter(Subscription.id == subscription_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not original_sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    # Validate email groups
    if not email_groups or len(email_groups) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide at least 2 email groups to split subscription",
        )

    # Collect all email IDs from groups
    all_group_email_ids = set()
    for group in email_groups:
        if "email_ids" not in group or not group["email_ids"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each group must have at least one email_id",
            )
        all_group_email_ids.update([UUID(eid) for eid in group["email_ids"]])

    # Get all emails currently linked to subscription
    original_email_ids = {email.id for email in original_sub.source_emails}

    # Validate that all provided email IDs belong to the subscription
    invalid_ids = all_group_email_ids - original_email_ids
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Some email IDs do not belong to this subscription: {invalid_ids}",
        )

    # Validate that all emails are accounted for
    if all_group_email_ids != original_email_ids:
        missing_ids = original_email_ids - all_group_email_ids
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All emails must be assigned to a group. Missing: {missing_ids}",
        )

    try:
        new_subscriptions = []

        # Create new subscriptions for each group
        for i, group in enumerate(email_groups):
            group_email_ids = [UUID(eid) for eid in group["email_ids"]]

            # Determine if this is the first group (keep original ID) or create new
            if i == 0:
                # First group keeps the original subscription
                target_sub = original_sub
                logger.info(
                    f"Keeping original subscription {target_sub.id} for first group"
                )
            else:
                # Create new subscription for other groups
                new_sub_data = {
                    "provider": original_sub.provider,
                    "amount": group.get("amount", original_sub.amount),
                    "currency": original_sub.currency,
                    "billing_cycle": original_sub.billing_cycle,
                    "category": original_sub.category,
                    "custom_label": group.get(
                        "custom_label", original_sub.custom_label
                    ),
                    "email_sender": original_sub.email_sender,
                    "renewal_date": original_sub.renewal_date,
                    "is_active": original_sub.is_active,
                    "mailbox_id": original_sub.mailbox_id,
                    "user_id": current_user.id,
                    "confidence_score": 1.0,  # Manual split has perfect confidence
                    "extraction_method": "manual_split",
                    "extraction_metadata": original_sub.extraction_metadata or {},
                }

                # Update service references if provided
                if "service_references" in group:
                    new_sub_data["extraction_metadata"]["service_references"] = group[
                        "service_references"
                    ]

                target_sub = Subscription(**new_sub_data)
                db.add(target_sub)
                db.flush()  # Get ID for junction table
                logger.info(f"Created new subscription {target_sub.id} for group {i+1}")

            # Update the first group with overrides if provided
            if i == 0:
                if "amount" in group:
                    target_sub.amount = group["amount"]
                if "custom_label" in group:
                    target_sub.custom_label = group["custom_label"]
                if "service_references" in group:
                    if not target_sub.extraction_metadata:
                        target_sub.extraction_metadata = {}
                    target_sub.extraction_metadata["service_references"] = group[
                        "service_references"
                    ]

            # Reassign emails to this subscription
            db.execute(
                subscription_emails.update()
                .where(subscription_emails.c.email_id.in_(group_email_ids))
                .where(subscription_emails.c.subscription_id == original_sub.id)
                .values(subscription_id=target_sub.id)
            )

            new_subscriptions.append(target_sub)

        db.commit()

        # Refresh all subscriptions to get latest data
        for sub in new_subscriptions:
            db.refresh(sub)

        logger.info(
            f"Split subscription {subscription_id} into {len(new_subscriptions)} subscriptions for user {current_user.id}"
        )

        return {
            "success": True,
            "message": f"Successfully split subscription into {len(new_subscriptions)} subscriptions",
            "subscriptions": [
                SubscriptionResponse.model_validate(sub) for sub in new_subscriptions
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to split subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to split subscription: {str(e)}",
        )
