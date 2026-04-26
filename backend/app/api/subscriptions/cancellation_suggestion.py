"""Cancellation-suggestion endpoints for subscriptions.

Handles: POST /{id}/accept-suggestion, POST /{id}/dismiss-suggestion.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import SubscriptionResponse
from app.security.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{subscription_id}/accept-suggestion", response_model=SubscriptionResponse
)
async def accept_cancellation_suggestion(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept an AI-generated cancellation suggestion.

    This will apply the suggested cancellation status to the subscription
    and clear the suggestion fields.
    """
    # Get subscription and verify ownership
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id, Subscription.user_id == current_user.id
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    # Check if there's a suggestion to accept
    if not subscription.suggested_cancellation_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending cancellation suggestion for this subscription",
        )

    try:
        # Apply the suggested status
        subscription.cancellation_status = subscription.suggested_cancellation_status
        subscription.cancellation_confirmed_at = datetime.now(timezone.utc)
        subscription.cancellation_notes = f"Auto-cancelled based on AI detection: {subscription.cancellation_suggestion_reason}"

        # Clear the suggestion fields
        subscription.suggested_cancellation_status = None
        subscription.cancellation_suggestion_reason = None
        subscription.cancellation_suggestion_created_at = None

        db.commit()
        db.refresh(subscription)

        logger.info(
            f"User {current_user.id} accepted cancellation suggestion for subscription {subscription_id}"
        )

        return SubscriptionResponse.model_validate(subscription)

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to accept cancellation suggestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept cancellation suggestion",
        )


@router.post("/{subscription_id}/dismiss-suggestion")
async def dismiss_cancellation_suggestion(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dismiss an AI-generated cancellation suggestion.

    This will clear the suggestion fields without changing the subscription status.
    """
    # Get subscription and verify ownership
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id, Subscription.user_id == current_user.id
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    # Check if there's a suggestion to dismiss
    if not subscription.suggested_cancellation_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending cancellation suggestion for this subscription",
        )

    try:
        # Clear the suggestion fields
        subscription.suggested_cancellation_status = None
        subscription.cancellation_suggestion_reason = None
        subscription.cancellation_suggestion_created_at = None

        db.commit()

        logger.info(
            f"User {current_user.id} dismissed cancellation suggestion for subscription {subscription_id}"
        )

        return {"success": True, "message": "Suggestion dismissed"}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to dismiss cancellation suggestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss cancellation suggestion",
        )
