"""Price history endpoints for subscriptions.

Handles: GET /{id}/price-history, GET /{id}/price-statistics.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.price_history import PriceHistoryResponse, PriceStatisticsResponse
from app.security.dependencies import get_current_user
from app.services.price_history_service import PriceHistoryService

router = APIRouter()


@router.get(
    "/{subscription_id}/price-history", response_model=List[PriceHistoryResponse]
)
async def get_subscription_price_history(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get price change history for a subscription.

    Returns all recorded price changes ordered by most recent first.
    """
    # Verify subscription ownership
    subscription = (
        db.query(Subscription)
        .join(Mailbox)
        .filter(Subscription.id == subscription_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    history = PriceHistoryService.get_subscription_price_history(
        db, str(subscription_id)
    )
    return history


@router.get(
    "/{subscription_id}/price-statistics", response_model=PriceStatisticsResponse
)
async def get_subscription_price_statistics(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get price change statistics for a subscription.

    Returns summary of all price changes including total increases/decreases,
    average change percentage, and current vs original price.
    """
    # Verify subscription ownership
    subscription = (
        db.query(Subscription)
        .join(Mailbox)
        .filter(Subscription.id == subscription_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    stats = PriceHistoryService.get_price_statistics(db, str(subscription_id))
    return stats
