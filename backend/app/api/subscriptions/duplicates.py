"""Duplicate-detection endpoint.

Handles: GET /duplicates.
"""

from collections import defaultdict
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_message import subscription_emails
from app.models.subscription import Subscription
from app.models.user import User
from app.security.dependencies import get_current_user

router = APIRouter()


@router.get("/duplicates", response_model=List[dict])
async def find_duplicate_subscriptions(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Find potential duplicate subscriptions for the current user.

    Groups subscriptions by provider and billing cycle to identify duplicates.
    """
    # Get all active subscriptions for user
    subscriptions = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.provider, Subscription.created_at)
        .all()
    )

    # Group by provider and billing cycle
    groups = defaultdict(list)
    for sub in subscriptions:
        # Create grouping key: provider + billing_cycle (or "unknown" if missing)
        key = f"{sub.provider.lower()}_{sub.billing_cycle or 'unknown'}"
        groups[key].append(sub)

    # Find groups with multiple subscriptions (potential duplicates)
    duplicate_groups = []
    for key, subs in groups.items():
        if len(subs) > 1:
            # Calculate similarity metrics
            provider = subs[0].provider
            billing_cycle = subs[0].billing_cycle

            # Check if amounts are similar (within 20%)
            amounts = [float(s.amount) for s in subs if s.amount is not None]
            similar_amounts = False
            if len(amounts) > 1:
                max_diff = max(amounts) - min(amounts)
                avg_amount = sum(amounts) / len(amounts)
                similar_amounts = (
                    (max_diff / avg_amount) < 0.20 if avg_amount > 0 else True
                )

            duplicate_groups.append(
                {
                    "provider": provider,
                    "billing_cycle": billing_cycle,
                    "count": len(subs),
                    "similar_amounts": similar_amounts,
                    "subscriptions": [
                        {
                            "id": str(s.id),
                            "provider": s.provider,
                            "amount": float(s.amount) if s.amount else None,
                            "currency": s.currency,
                            "billing_cycle": s.billing_cycle,
                            "custom_label": s.custom_label,
                            "created_at": s.created_at.isoformat(),
                            "renewal_date": (
                                s.renewal_date.isoformat() if s.renewal_date else None
                            ),
                            "is_active": s.is_active,
                            "email_count": db.query(func.count())
                            .select_from(subscription_emails)
                            .filter(subscription_emails.c.subscription_id == s.id)
                            .scalar(),
                        }
                        for s in subs
                    ],
                }
            )

    return duplicate_groups
