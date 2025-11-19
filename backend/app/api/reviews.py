"""
Review suggestions API endpoints.
Provides intelligent suggestions for which subscriptions to review or cancel.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.security.dependencies import get_current_user
from app.models.user import User
from app.schemas.cancellation import ReviewSuggestionsResponse
from app.services.review_suggestions import ReviewSuggestionsService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/suggestions", response_model=ReviewSuggestionsResponse)
async def get_review_suggestions(
    include_dismissed: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get intelligent review suggestions for user's subscriptions.

    Analyzes all active subscriptions and suggests which ones to review based on:
    - **Trial ending** (CRITICAL): Trials ending today or within 1 day
    - **Trial ending soon** (HIGH): Trials ending within 7 days
    - **Likely unused** (MEDIUM): No email activity in 30+ days
    - **Expensive unused** (HIGH): Costs >$20/month with no recent activity
    - **Duplicate provider** (MEDIUM): Multiple subscriptions to same provider

    **Priority Levels:**
    - `critical`: Immediate action needed (trials ending today/tomorrow)
    - `high`: Important to review soon (expensive unused, trials ending this week)
    - `medium`: Should review (unused, duplicates)
    - `low`: Optional review

    **Suggestions are sorted by:**
    1. Priority (critical first)
    2. Action date (urgent first)

    **Parameters:**
    - `include_dismissed`: Include previously dismissed suggestions (default: false)

    **Returns:**
    - List of review suggestions with actionable messages
    - Count of critical and high-priority suggestions
    - Total suggestion count

    **Example Response:**
    ```json
    {
        "suggestions": [
            {
                "subscription_id": "...",
                "provider": "Netflix",
                "reason": "trial_ending",
                "priority": "critical",
                "message": "🚨 Your Netflix trial ends TODAY! Cancel now to avoid charges.",
                "action_by_date": "2024-12-31T00:00:00Z",
                "amount": 15.99,
                "currency": "USD",
                "billing_cycle": "monthly"
            }
        ],
        "total_count": 5,
        "critical_count": 1,
        "high_priority_count": 2
    }
    ```

    **Integration:**
    Use with `/api/cancellation/subscriptions/{id}/status` to act on suggestions.
    """
    logger.info(f"User {current_user.id} requesting review suggestions")

    try:
        service = ReviewSuggestionsService(db)
        suggestions = service.get_review_suggestions(
            user_id=current_user.id,
            include_dismissed=include_dismissed
        )

        logger.info(
            f"Returning {suggestions.total_count} suggestions to user {current_user.id}: "
            f"{suggestions.critical_count} critical, {suggestions.high_priority_count} high priority"
        )

        return suggestions

    except Exception as e:
        logger.error(f"Failed to generate suggestions for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate review suggestions. Please try again later."
        )
