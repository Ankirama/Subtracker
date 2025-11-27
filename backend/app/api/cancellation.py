"""
Cancellation workflow API endpoints.
Provides AI-powered cancellation research and subscription cancellation management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.security.dependencies import get_current_user
from app.models.user import User
from app.models.subscription import Subscription
from app.models.mailbox import Mailbox
from app.models.provider_cancellation import ProviderCancellationInfo
from app.schemas.cancellation import (
    AIResearchRequest,
    AIResearchResponse,
    ProviderCancellationInfoResponse,
    SubscriptionCancellationInfo,
    SubscriptionCancellationStatusUpdate,
    CancellationStatus,
    DifficultyRating,
)
from app.services.cancellation_research import CancellationResearchService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_subscription_ownership(
    subscription_id: UUID, user_id: UUID, db: Session
) -> Subscription:
    """
    Verify that the subscription belongs to the current user.

    Args:
        subscription_id: Subscription UUID to verify
        user_id: Current user's UUID
        db: Database session

    Returns:
        Subscription if owned by user

    Raises:
        HTTPException: 404 if not found, 403 if not owned
    """
    stmt = (
        select(Subscription)
        .join(Mailbox)
        .where(Subscription.id == subscription_id, Mailbox.user_id == user_id)
    )
    subscription = db.execute(stmt).scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription {subscription_id} not found or access denied",
        )

    return subscription


@router.post(
    "/research", response_model=AIResearchResponse, status_code=status.HTTP_200_OK
)
async def research_cancellation(
    request: AIResearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Research cancellation instructions for a provider using AI.

    Uses GPT-4o-mini to research how to cancel a subscription service.
    Results are cached for 90 days to optimize costs.

    **Parameters:**
    - `provider_name`: Name of the subscription provider (e.g., "Netflix", "Spotify")
    - `force_refresh`: Force new AI research even if cached data exists

    **Returns:**
    - Cancellation instructions with difficulty rating, steps, timing, gotchas
    - AI confidence score (0.0-1.0) indicating research quality
    - Whether result was cached or freshly researched

    **Example:**
    ```json
    {
        "provider_name": "Netflix",
        "force_refresh": false
    }
    ```
    """
    logger.info(
        f"User {current_user.id} researching cancellation for {request.provider_name}"
    )

    try:
        service = CancellationResearchService(db)
        result = await service.research_provider(
            provider_name=request.provider_name, force_refresh=request.force_refresh
        )

        # Convert service result to response schema
        return AIResearchResponse(
            provider_name=result["provider_name"],
            cancellation_url=result.get("cancellation_url"),
            difficulty_rating=DifficultyRating(result["difficulty"]),
            instructions=result.get("instructions", []),
            requires_phone_call=result.get("requires_phone", False),
            requires_chat=result.get("requires_chat", False),
            allows_pause=result.get("allows_pause", False),
            pause_instructions=result.get("pause_instructions"),
            additional_notes=result.get("additional_notes"),
            estimated_time_minutes=result.get("estimated_minutes"),
            cancellation_gotchas=result.get("gotchas"),
            ai_confidence_score=result.get("confidence", 0.0),
            sources_consulted=(
                result.get("sources")
                if isinstance(result.get("sources"), list)
                else None
            ),
            research_timestamp=datetime.utcnow(),
        )

    except ValueError as e:
        logger.error(f"Invalid research request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Research failed for {request.provider_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to research cancellation instructions. Please try again later.",
        )


@router.get(
    "/providers/{provider_name}", response_model=ProviderCancellationInfoResponse
)
async def get_provider_cancellation_info(
    provider_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get cached cancellation information for a specific provider.

    Returns previously researched cancellation instructions if available.
    If no cached data exists, use the `/research` endpoint to generate new instructions.

    **Parameters:**
    - `provider_name`: Name of the provider (case-insensitive)

    **Returns:**
    - Cached cancellation instructions with metadata
    - Verification status and last verification date
    - AI confidence score and research timestamp

    **Note:** Data may be up to 90 days old. Check `needs_reverification` field.
    """
    logger.info(
        f"User {current_user.id} fetching cancellation info for {provider_name}"
    )

    stmt = select(ProviderCancellationInfo).where(
        ProviderCancellationInfo.provider_name.ilike(provider_name)
    )
    provider_info = db.execute(stmt).scalar_one_or_none()

    if not provider_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cancellation information found for {provider_name}. "
            f"Use the /research endpoint to generate instructions.",
        )

    return provider_info


@router.get(
    "/subscriptions/{subscription_id}", response_model=SubscriptionCancellationInfo
)
async def get_subscription_cancellation_info(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get cancellation information for a specific subscription.

    Combines the subscription's cancellation status with provider cancellation instructions.

    **Parameters:**
    - `subscription_id`: UUID of the subscription

    **Returns:**
    - Subscription cancellation status and notes
    - Provider cancellation instructions (if available)
    - Dates for cancellation requests and confirmations

    **Authorization:** User must own the subscription's mailbox
    """
    logger.info(
        f"User {current_user.id} fetching cancellation info for subscription {subscription_id}"
    )

    # Verify ownership
    subscription = verify_subscription_ownership(subscription_id, current_user.id, db)

    # Get provider cancellation info if available
    provider_info = None
    if subscription.provider:
        stmt = select(ProviderCancellationInfo).where(
            ProviderCancellationInfo.provider_name.ilike(subscription.provider)
        )
        provider_info = db.execute(stmt).scalar_one_or_none()

    return SubscriptionCancellationInfo(
        subscription_id=subscription.id,
        provider=subscription.provider or "Unknown",
        cancellation_status=CancellationStatus(subscription.cancellation_status),
        cancellation_requested_at=subscription.cancellation_requested_at,
        cancellation_confirmed_at=subscription.cancellation_confirmed_at,
        cancellation_notes=subscription.cancellation_notes,
        provider_info=provider_info,
    )


@router.patch(
    "/subscriptions/{subscription_id}/status",
    response_model=SubscriptionCancellationInfo,
)
async def update_subscription_cancellation_status(
    subscription_id: UUID,
    update: SubscriptionCancellationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a subscription's cancellation status.

    Track the cancellation workflow: active → pending_cancellation → cancelled

    **Parameters:**
    - `subscription_id`: UUID of the subscription
    - `cancellation_status`: New status (active, pending_cancellation, paused, cancelled)
    - `cancellation_notes`: Optional notes about the cancellation

    **Status Flow:**
    - `active`: Subscription is active and not being cancelled
    - `pending_cancellation`: User has requested cancellation but it's not confirmed yet
    - `paused`: Subscription is temporarily paused
    - `cancelled`: Subscription has been successfully cancelled

    **Returns:**
    - Updated subscription cancellation information

    **Authorization:** User must own the subscription's mailbox
    """
    logger.info(
        f"User {current_user.id} updating cancellation status for subscription {subscription_id}"
    )

    # Verify ownership
    subscription = verify_subscription_ownership(subscription_id, current_user.id, db)

    # Update cancellation status
    old_status = subscription.cancellation_status
    subscription.cancellation_status = update.cancellation_status.value

    # Update notes if provided
    if update.cancellation_notes is not None:
        subscription.cancellation_notes = update.cancellation_notes

    # Track timestamps
    now = datetime.utcnow()

    if update.cancellation_status == CancellationStatus.PENDING_CANCELLATION:
        # User has requested cancellation
        if not subscription.cancellation_requested_at:
            subscription.cancellation_requested_at = now
            logger.info(
                f"Subscription {subscription_id} cancellation requested at {now}"
            )

    elif update.cancellation_status == CancellationStatus.CANCELLED:
        # Cancellation confirmed
        if not subscription.cancellation_confirmed_at:
            subscription.cancellation_confirmed_at = now
            logger.info(
                f"Subscription {subscription_id} cancellation confirmed at {now}"
            )
        if not subscription.cancellation_requested_at:
            subscription.cancellation_requested_at = now

    elif update.cancellation_status == CancellationStatus.ACTIVE:
        # Reset cancellation timestamps if going back to active
        subscription.cancellation_requested_at = None
        subscription.cancellation_confirmed_at = None
        logger.info(f"Subscription {subscription_id} reactivated from {old_status}")

    db.commit()
    db.refresh(subscription)

    logger.info(
        f"Subscription {subscription_id} status updated: {old_status} → {update.cancellation_status.value}"
    )

    # Get provider info for response
    provider_info = None
    if subscription.provider:
        stmt = select(ProviderCancellationInfo).where(
            ProviderCancellationInfo.provider_name.ilike(subscription.provider)
        )
        provider_info = db.execute(stmt).scalar_one_or_none()

    return SubscriptionCancellationInfo(
        subscription_id=subscription.id,
        provider=subscription.provider or "Unknown",
        cancellation_status=CancellationStatus(subscription.cancellation_status),
        cancellation_requested_at=subscription.cancellation_requested_at,
        cancellation_confirmed_at=subscription.cancellation_confirmed_at,
        cancellation_notes=subscription.cancellation_notes,
        provider_info=provider_info,
    )
