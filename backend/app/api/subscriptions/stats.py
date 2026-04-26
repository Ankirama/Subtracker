"""Subscription stats endpoint.

Handles: GET /stats.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import SubscriptionResponse, SubscriptionStats
from app.security.dependencies import get_current_user
from app.services.cost_projection import project_monthly_cost, project_yearly_cost

router = APIRouter()


@router.get("/stats", response_model=SubscriptionStats)
async def get_subscription_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    exclude_trials: bool = Query(
        True, description="Exclude trial-only subscriptions (default: true)"
    ),
):
    """
    Get subscription statistics for the current user.

    Includes total costs, category breakdown, and upcoming renewals.
    By default, excludes trial-only subscriptions that were never converted.
    """
    # Get all active subscriptions (excluding trials by default)
    query = (
        db.query(Subscription)
        .join(Mailbox)
        .filter(Mailbox.user_id == current_user.id, Subscription.is_active)
    )

    # Apply trial filter
    if exclude_trials:
        query = query.filter(Subscription.is_confirmed)

    subscriptions = query.all()

    total_subscriptions = len(subscriptions)
    active_subscriptions = len([s for s in subscriptions if s.is_active])

    # Calculate costs
    monthly_cost = 0.0
    yearly_cost = 0.0

    for sub in subscriptions:
        monthly_cost += project_monthly_cost(sub.amount, sub.billing_cycle)
        yearly_cost += project_yearly_cost(sub.amount, sub.billing_cycle)

    # Category breakdown
    by_category = {}
    for sub in subscriptions:
        category = sub.category or "other"
        if category not in by_category:
            by_category[category] = {"count": 0, "total": 0.0}

        by_category[category]["count"] += 1

        # Calculate monthly cost for this subscription
        by_category[category]["total"] += project_monthly_cost(
            sub.amount, sub.billing_cycle
        )

    # Billing cycle breakdown
    by_billing_cycle = {}
    for sub in subscriptions:
        cycle = sub.billing_cycle or "unknown"
        by_billing_cycle[cycle] = by_billing_cycle.get(cycle, 0) + 1

    # Upcoming renewals (next 30 days) - use computed next_renewal_date
    today = datetime.now().date()
    thirty_days = today + timedelta(days=30)
    upcoming = [
        s
        for s in subscriptions
        if s.next_renewal_date and today <= s.next_renewal_date <= thirty_days
    ]
    upcoming.sort(
        key=lambda x: (
            x.next_renewal_date if x.next_renewal_date else datetime.max.date()
        )
    )

    return SubscriptionStats(
        total_subscriptions=total_subscriptions,
        active_subscriptions=active_subscriptions,
        total_monthly_cost=round(monthly_cost, 2),
        total_yearly_cost=round(yearly_cost, 2),
        by_category=by_category,
        by_billing_cycle=by_billing_cycle,
        upcoming_renewals=[
            SubscriptionResponse.model_validate(s) for s in upcoming[:5]
        ],
    )
