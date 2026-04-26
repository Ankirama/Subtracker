"""Subscription feedback endpoint.

Handles: POST /feedback.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.subscription_feedback import SubscriptionFeedback
from app.models.user import User
from app.schemas.subscription import FeedbackCreate, FeedbackResponse
from app.security.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED
)
async def create_subscription_feedback(
    feedback_data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create feedback for an AI-detected subscription that user is rejecting.

    This captures:
    - Why the user is rejecting the subscription
    - Full snapshot of subscription data before deletion
    - AI classification metadata for analysis
    - Related email IDs that led to the detection

    Used to improve future AI classification accuracy.
    """
    try:
        # Get the subscription to verify ownership and capture snapshot
        subscription = (
            db.query(Subscription)
            .join(Mailbox)
            .options(joinedload(Subscription.source_emails))
            .filter(
                Subscription.id == feedback_data.subscription_id,
                Mailbox.user_id == current_user.id,
            )
            .first()
        )

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found or not authorized",
            )

        # Create subscription snapshot
        subscription_snapshot = {
            "provider": subscription.provider,
            "amount": float(subscription.amount) if subscription.amount else None,
            "currency": subscription.currency,
            "billing_cycle": subscription.billing_cycle,
            "category": subscription.category,
            "custom_label": subscription.custom_label,
            "email_sender": subscription.email_sender,
            "renewal_date": (
                subscription.renewal_date.isoformat()
                if subscription.renewal_date
                else None
            ),
            "is_active": subscription.is_active,
            "confidence_score": (
                float(subscription.confidence_score)
                if subscription.confidence_score
                else None
            ),
            "extraction_method": subscription.extraction_method,
            "first_detected_at": (
                subscription.first_detected_at.isoformat()
                if subscription.first_detected_at
                else None
            ),
            "last_confirmed_at": (
                subscription.last_confirmed_at.isoformat()
                if subscription.last_confirmed_at
                else None
            ),
        }

        # Get AI classification data if available
        ai_classification_data = None
        if subscription.extraction_metadata:
            ai_classification_data = subscription.extraction_metadata

        # Get source email IDs (handle case where relationship might not be loaded)
        try:
            source_email_ids = (
                [email.id for email in subscription.source_emails]
                if subscription.source_emails
                else []
            )
        except Exception as e:
            logger.warning(
                f"Could not load source_emails for subscription {subscription.id}: {e}"
            )
            source_email_ids = []

        # Create feedback record
        feedback = SubscriptionFeedback(
            user_id=current_user.id,
            subscription_id=feedback_data.subscription_id,
            feedback_type=feedback_data.feedback_type,
            feedback_text=feedback_data.feedback_text,
            subscription_snapshot=subscription_snapshot,
            ai_classification_data=ai_classification_data,
            source_email_ids=source_email_ids,
        )

        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        logger.info(
            f"Feedback created for subscription {feedback_data.subscription_id} "
            f"by user {current_user.id}: {feedback_data.feedback_type}"
        )

        return feedback

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create feedback: {str(e)}",
        )
