"""
Subscription API endpoints for managing discovered subscriptions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from uuid import UUID
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from app.database import get_db
from app.models.user import User
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.email_message import subscription_emails
from app.models.subscription_feedback import SubscriptionFeedback
from app.models.price_history import PriceHistory
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    SubscriptionStats,
    SubscriptionDetailResponse,
    EmailMessageResponse,
    AnalyticsResponse,
    MonthlySpendingData,
    CategorySpendingTrend,
    FeedbackCreate,
    FeedbackResponse,
)
from app.schemas.price_history import PriceHistoryResponse, PriceStatisticsResponse
from app.services.price_history_service import PriceHistoryService
from app.security.dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_mailbox_ownership(mailbox_id: UUID, user_id: UUID, db: Session) -> Mailbox:
    """Verify that the mailbox belongs to the current user."""
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == user_id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found or not authorized",
        )

    return mailbox


@router.post(
    "/", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED
)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually create a subscription.

    Usually subscriptions are auto-detected, but this allows manual entry.
    """
    # Verify mailbox ownership
    verify_mailbox_ownership(subscription_data.mailbox_id, current_user.id, db)

    # Check for duplicate
    existing = (
        db.query(Subscription)
        .filter(
            Subscription.mailbox_id == subscription_data.mailbox_id,
            Subscription.provider == subscription_data.provider,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subscription for {subscription_data.provider} already exists in this mailbox",
        )

    # Create subscription
    new_subscription = Subscription(
        **subscription_data.model_dump(),
        user_id=current_user.id,
        confidence_score=1.0,  # Manual entry has perfect confidence
        extraction_method="manual",
    )

    db.add(new_subscription)
    db.commit()
    db.refresh(new_subscription)

    logger.info(f"Manually created subscription: {new_subscription.id}")
    return SubscriptionResponse.model_validate(new_subscription)


@router.get("/", response_model=SubscriptionListResponse)
async def list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    mailbox_id: UUID = None,
    status_filter: str = Query(None, alias="status"),
    category: str = None,
    exclude_trials: bool = Query(
        True, description="Exclude trial-only subscriptions (default: true)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """
    List all subscriptions for the current user.

    Supports filtering by mailbox, status, category, and trial exclusion.
    By default, excludes trial-only subscriptions that were never converted.
    """
    # Base query: all subscriptions from user's mailboxes
    query = (
        db.query(Subscription).join(Mailbox).filter(Mailbox.user_id == current_user.id)
    )

    # Apply trial filter (default: exclude trials)
    if exclude_trials:
        query = query.filter(Subscription.is_confirmed)

    # Apply filters
    if mailbox_id:
        verify_mailbox_ownership(mailbox_id, current_user.id, db)
        query = query.filter(Subscription.mailbox_id == mailbox_id)

    if status_filter:
        # Convert status filter to boolean for is_active field
        if status_filter.lower() == "active":
            query = query.filter(Subscription.is_active)
        elif status_filter.lower() == "inactive":
            query = query.filter(not Subscription.is_active)

    if category:
        query = query.filter(Subscription.category == category)

    # Get total count
    total = query.count()

    # Paginate
    subscriptions = (
        query.order_by(Subscription.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return SubscriptionListResponse(
        subscriptions=[SubscriptionResponse.model_validate(s) for s in subscriptions],
        total=total,
        page=page,
        page_size=page_size,
        has_more=total > (page * page_size),
    )


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
        if sub.amount and sub.billing_cycle:
            amount = float(sub.amount)
            if sub.billing_cycle == "monthly":
                monthly_cost += amount
                yearly_cost += amount * 12
            elif sub.billing_cycle == "yearly":
                yearly_cost += amount
                monthly_cost += amount / 12
            elif sub.billing_cycle == "weekly":
                monthly_cost += amount * 4.33  # Average weeks per month
                yearly_cost += amount * 52

    # Category breakdown
    by_category = {}
    for sub in subscriptions:
        category = sub.category or "other"
        if category not in by_category:
            by_category[category] = {"count": 0, "total": 0.0}

        by_category[category]["count"] += 1

        # Calculate monthly cost for this subscription
        if sub.amount and sub.billing_cycle:
            amount = float(sub.amount)
            if sub.billing_cycle == "monthly":
                by_category[category]["total"] += amount
            elif sub.billing_cycle == "yearly":
                by_category[category]["total"] += amount / 12
            elif sub.billing_cycle == "weekly":
                by_category[category]["total"] += amount * 4.33

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
        monthly_cost = 0.0
        if sub.amount and sub.billing_cycle:
            amount = float(sub.amount)
            if sub.billing_cycle == "monthly":
                monthly_cost = amount
            elif sub.billing_cycle == "yearly":
                monthly_cost = amount / 12
            elif sub.billing_cycle == "weekly":
                monthly_cost = amount * 4.33
            elif sub.billing_cycle == "quarterly":
                monthly_cost = amount / 3
            elif sub.billing_cycle == "biannual":
                monthly_cost = amount / 6

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


@router.get("/{subscription_id}", response_model=SubscriptionDetailResponse)
async def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific subscription by ID with detailed information including source emails.
    """
    # Query with eager loading of source emails
    subscription = (
        db.query(Subscription)
        .options(joinedload(Subscription.source_emails))
        .join(Mailbox)
        .filter(Subscription.id == subscription_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    # Build the detailed response with source emails and junction table data
    source_emails_data = []

    # Query the junction table to get extraction metadata
    for email in subscription.source_emails:
        # Get the junction table data
        junction_data = db.execute(
            subscription_emails.select().where(
                subscription_emails.c.subscription_id == subscription.id,
                subscription_emails.c.email_id == email.id,
            )
        ).first()

        source_emails_data.append(
            {
                "email": EmailMessageResponse.model_validate(email),
                "extraction_role": (
                    junction_data.extraction_role if junction_data else None
                ),
                "extraction_data": (
                    junction_data.extraction_data if junction_data else None
                ),
                "created_at": (
                    junction_data.created_at if junction_data else email.created_at
                ),
            }
        )

    # Create the response model
    response_data = SubscriptionResponse.model_validate(subscription).model_dump()
    response_data["source_emails"] = source_emails_data

    return SubscriptionDetailResponse(**response_data)


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    update_data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update subscription details.

    Allows updating any subscription field.
    """
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

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)

    # If user is manually changing is_active status, set manual_status_override flag
    if (
        "is_active" in update_dict
        and update_dict["is_active"] != subscription.is_active
    ):
        update_dict["manual_status_override"] = True

    for field, value in update_dict.items():
        setattr(subscription, field, value)

    subscription.updated_at = datetime.now()
    db.commit()
    db.refresh(subscription)

    logger.info(f"Updated subscription: {subscription_id}")
    return SubscriptionResponse.model_validate(subscription)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a subscription.

    This removes the subscription record permanently.
    """
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

    db.delete(subscription)
    db.commit()

    logger.info(f"Deleted subscription: {subscription_id}")
    return None


@router.post("/update-status")
async def update_subscription_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    mailbox_id: UUID = None,
):
    """
    Manually update subscription active/inactive status based on last email confirmation.

    This runs the same logic that executes automatically after email sync:
    - Checks last_confirmed_at against billing cycle + grace period
    - Marks subscriptions as active if recently confirmed
    - Marks subscriptions as inactive if no recent confirmation

    If mailbox_id is provided, updates only that mailbox's subscriptions.
    Otherwise, updates all mailboxes for the current user.
    """
    from app.tasks.email_sync import update_subscription_statuses

    try:
        # Get mailboxes to update
        mailboxes_query = db.query(Mailbox).filter(Mailbox.user_id == current_user.id)

        if mailbox_id:
            verify_mailbox_ownership(mailbox_id, current_user.id, db)
            mailboxes_query = mailboxes_query.filter(Mailbox.id == mailbox_id)

        mailboxes = mailboxes_query.all()

        if not mailboxes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No mailboxes found"
            )

        # Update status for each mailbox
        total_activated = 0
        total_deactivated = 0
        mailbox_results = []

        for mailbox in mailboxes:
            result = update_subscription_statuses(db, mailbox.id)
            total_activated += result["activated"]
            total_deactivated += result["deactivated"]

            mailbox_results.append(
                {
                    "mailbox_id": str(mailbox.id),
                    "mailbox_email": mailbox.email_address,
                    "activated": result["activated"],
                    "deactivated": result["deactivated"],
                }
            )

        logger.info(
            f"Manual status update for user {current_user.id}: {total_activated} activated, {total_deactivated} deactivated"
        )

        return {
            "success": True,
            "total_activated": total_activated,
            "total_deactivated": total_deactivated,
            "mailboxes_updated": len(mailboxes),
            "details": mailbox_results,
            "message": f"Updated {total_activated + total_deactivated} subscription statuses",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update subscription status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription status: {str(e)}",
        )


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


# Price History Endpoints


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


@router.post("/update-renewal-status")
async def update_subscription_renewal_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Update renewal dates and active status for all user's subscriptions.

    Uses the RenewalCalculator service to:
    - Extract renewal dates from email content (provider-specific patterns)
    - Calculate renewal dates based on billing cycles
    - Detect inactive subscriptions (>2 billing cycles without emails)
    - Update is_active status accordingly

    Returns counts of total, activated, and deactivated subscriptions.
    """
    from app.services.renewal_calculator import (
        RenewalCalculator,
        get_subscription_emails,
    )

    # Get all user's subscriptions
    subscriptions = (
        db.query(Subscription)
        .join(Mailbox)
        .filter(Mailbox.user_id == current_user.id)
        .all()
    )

    renewal_calc = RenewalCalculator(db)

    total_processed = 0
    total_activated = 0
    total_deactivated = 0
    errors = []

    for subscription in subscriptions:
        try:
            # Get all emails for this subscription
            subscription_emails_data = get_subscription_emails(db, subscription.id)

            if not subscription_emails_data:
                logger.warning(f"No emails found for subscription {subscription.id}")
                continue

            # Extract dates and contents
            email_dates = [e["date"] for e in subscription_emails_data]
            email_contents = [
                e["body_html"] or e["body_text"] or "" for e in subscription_emails_data
            ]

            # Store old status for comparison
            old_active = subscription.is_active

            # Calculate renewal date, active status, trial status, and confirmation
            renewal_date, is_active, trial_status, is_confirmed = (
                renewal_calc.calculate_renewal_info(
                    provider=subscription.provider,
                    billing_cycle=subscription.billing_cycle,
                    email_dates=email_dates,
                    email_contents=email_contents,
                    extraction_metadata=subscription.extraction_metadata,
                )
            )

            # Update subscription
            if renewal_date:
                subscription.renewal_date = renewal_date
                logger.info(
                    f"Updated renewal date for {subscription.provider}: {renewal_date.strftime('%Y-%m-%d')}"
                )

            subscription.is_active = is_active
            subscription.trial_status = trial_status
            subscription.is_confirmed = is_confirmed

            # Track status changes
            if old_active and not is_active:
                total_deactivated += 1
                logger.info(f"Deactivated {subscription.provider}")
            elif not old_active and is_active:
                total_activated += 1
                logger.info(f"Activated {subscription.provider}")

            total_processed += 1

        except Exception as e:
            error_msg = f"Error updating {subscription.provider}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue

    db.commit()

    response = {
        "success": True,
        "total_processed": total_processed,
        "total_activated": total_activated,
        "total_deactivated": total_deactivated,
        "message": f"Updated {total_processed} subscriptions: {total_activated} activated, {total_deactivated} deactivated",
    }

    if errors:
        response["errors"] = errors

    return response


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
                logger.info(f"Keeping original subscription {target_sub.id} for first group")
            else:
                # Create new subscription for other groups
                new_sub_data = {
                    "provider": original_sub.provider,
                    "amount": group.get("amount", original_sub.amount),
                    "currency": original_sub.currency,
                    "billing_cycle": original_sub.billing_cycle,
                    "category": original_sub.category,
                    "custom_label": group.get("custom_label", original_sub.custom_label),
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
