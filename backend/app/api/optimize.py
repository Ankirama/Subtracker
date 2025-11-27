"""
Subscription optimization API endpoints.

Provides AI-powered recommendations and insights for subscription optimization.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.models.user import User
from app.models.subscription import Subscription
from app.models.mailbox import Mailbox
from app.security.dependencies import get_current_user
from app.services.ai_optimizer import AIOptimizer
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/recommendations", response_model=Dict[str, Any])
async def get_optimization_recommendations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get AI-powered subscription optimization recommendations.

    Returns:
        Dict with recommendations, potential savings, and insights
    """
    try:
        # Get all user's mailboxes
        mailbox_ids = (
            db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        )
        mailbox_ids = [m[0] for m in mailbox_ids]

        if not mailbox_ids:
            return {
                "total_recommendations": 0,
                "potential_savings": 0.0,
                "recommendations": [],
                "insights": [
                    "No subscriptions to analyze. Connect a mailbox to get started!"
                ],
            }

        # Get active subscriptions
        active_subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.mailbox_id.in_(mailbox_ids), Subscription.is_active
            )
            .all()
        )

        if not active_subscriptions:
            return {
                "total_recommendations": 0,
                "potential_savings": 0.0,
                "recommendations": [],
                "insights": ["No active subscriptions to analyze."],
            }

        # Run AI analysis
        analysis = AIOptimizer.analyze_subscriptions(
            db, current_user, active_subscriptions
        )

        logger.info(
            f"Generated {analysis['total_recommendations']} recommendations for user {current_user.id}"
        )
        return analysis

    except Exception as e:
        logger.error(
            f"Failed to generate optimization recommendations for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
        )
