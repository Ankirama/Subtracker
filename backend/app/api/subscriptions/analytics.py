"""Subscription analytics endpoint.

Handles: GET /analytics/trends.
"""

import logging
from collections import defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    AnalyticsResponse,
    CategorySpendingTrend,
    MonthlySpendingData,
)
from app.security.dependencies import get_current_user
from app.services.cost_projection import project_monthly_cost

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analytics/trends", response_model=AnalyticsResponse)
async def get_analytics_trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    months: int = Query(12, ge=3, le=24, description="Number of months to analyze"),
):
    """
    Get detailed analytics and spending trends over time.

    Analyzes subscription history to provide:
    - Monthly spending trends
    - Subscription count changes over time
    - Category spending patterns
    - Peak spending periods
    """
    # Get all subscriptions (active and inactive) for the user
    all_subscriptions = (
        db.query(Subscription)
        .join(Mailbox)
        .filter(Mailbox.user_id == current_user.id)
        .all()
    )

    # Calculate date range
    today = datetime.now().date()
    start_date = today - relativedelta(months=months)

    # Initialize monthly data structure
    monthly_data = {}
    current_month = start_date.replace(day=1)

    while current_month <= today:
        month_key = f"{current_month.year}-{current_month.month:02d}"
        monthly_data[month_key] = {
            "year": current_month.year,
            "month_num": current_month.month,
            "month": current_month.strftime("%b %Y"),
            "total_cost": 0.0,
            "subscription_count": 0,
            "new_subscriptions": 0,
            "cancelled_subscriptions": 0,
            "active_subs": set(),
            "categories": defaultdict(float),
        }
        current_month += relativedelta(months=1)

    # Process each subscription
    for sub in all_subscriptions:
        first_detected = sub.first_detected_at.date() if sub.first_detected_at else None
        last_confirmed = sub.last_confirmed_at.date() if sub.last_confirmed_at else None

        if not first_detected:
            continue

        # Calculate monthly cost for this subscription
        monthly_cost = project_monthly_cost(sub.amount, sub.billing_cycle)

        # Track subscription across months it was active
        sub_start = max(first_detected.replace(day=1), start_date.replace(day=1))
        sub_end = (
            last_confirmed.replace(day=1) if last_confirmed else today.replace(day=1)
        )

        current = sub_start
        while current <= sub_end and current <= today.replace(day=1):
            month_key = f"{current.year}-{current.month:02d}"

            if month_key in monthly_data:
                # Add to monthly cost
                monthly_data[month_key]["total_cost"] += monthly_cost
                monthly_data[month_key]["active_subs"].add(sub.id)

                # Track category spending
                category = sub.category or "other"
                monthly_data[month_key]["categories"][category] += monthly_cost

                # Track new subscriptions
                if current == sub_start:
                    monthly_data[month_key]["new_subscriptions"] += 1

                # Track cancelled subscriptions
                if last_confirmed and current == sub_end and not sub.is_active:
                    monthly_data[month_key]["cancelled_subscriptions"] += 1

            current += relativedelta(months=1)

    # Convert to response format
    monthly_spending = []
    total_spent = 0.0
    peak_month = None
    peak_cost = 0.0

    for month_key in sorted(monthly_data.keys()):
        data = monthly_data[month_key]
        data["subscription_count"] = len(data["active_subs"])

        monthly_spending.append(
            MonthlySpendingData(
                month=data["month"],
                year=data["year"],
                month_num=data["month_num"],
                total_cost=round(data["total_cost"], 2),
                subscription_count=data["subscription_count"],
                new_subscriptions=data["new_subscriptions"],
                cancelled_subscriptions=data["cancelled_subscriptions"],
            )
        )

        total_spent += data["total_cost"]

        if data["total_cost"] > peak_cost:
            peak_cost = data["total_cost"]
            peak_month = data["month"]

    # Calculate category trends
    category_trends = []
    all_categories = set()

    for data in monthly_data.values():
        all_categories.update(data["categories"].keys())

    for category in all_categories:
        monthly_category_data = []
        for month_key in sorted(monthly_data.keys()):
            data = monthly_data[month_key]
            monthly_category_data.append(
                {
                    "month": data["month"],
                    "amount": round(data["categories"].get(category, 0.0), 2),
                }
            )

        category_trends.append(
            CategorySpendingTrend(category=category, monthly_data=monthly_category_data)
        )

    # Calculate average monthly cost
    avg_monthly = total_spent / len(monthly_data) if monthly_data else 0.0

    logger.info(
        f"Generated analytics for user {current_user.id}: {len(monthly_spending)} months, {len(category_trends)} categories"
    )

    return AnalyticsResponse(
        monthly_spending=monthly_spending,
        category_trends=category_trends,
        total_spent=round(total_spent, 2),
        average_monthly_cost=round(avg_monthly, 2),
        peak_month=peak_month,
        peak_month_cost=round(peak_cost, 2) if peak_cost > 0 else None,
    )
