"""
Subscription API endpoints for managing discovered subscriptions.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from app.database import get_db
from app.models.user import User
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.email_message import EmailMessage, subscription_emails
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    SubscriptionStats,
    SubscriptionDetailResponse,
    SubscriptionEmailLink,
    EmailMessageResponse
)
from app.security.dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_mailbox_ownership(mailbox_id: UUID, user_id: UUID, db: Session) -> Mailbox:
    """Verify that the mailbox belongs to the current user."""
    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == user_id
    ).first()
    
    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found or not authorized"
        )
    
    return mailbox


@router.post("/", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually create a subscription.
    
    Usually subscriptions are auto-detected, but this allows manual entry.
    """
    # Verify mailbox ownership
    verify_mailbox_ownership(subscription_data.mailbox_id, current_user.id, db)
    
    # Check for duplicate
    existing = db.query(Subscription).filter(
        Subscription.mailbox_id == subscription_data.mailbox_id,
        Subscription.provider == subscription_data.provider
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subscription for {subscription_data.provider} already exists in this mailbox"
        )
    
    # Create subscription
    new_subscription = Subscription(
        **subscription_data.model_dump(),
        confidence_score=1.0,  # Manual entry has perfect confidence
        extraction_method='manual'
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100)
):
    """
    List all subscriptions for the current user.
    
    Supports filtering by mailbox, status, and category.
    """
    # Base query: all subscriptions from user's mailboxes
    query = db.query(Subscription).join(Mailbox).filter(
        Mailbox.user_id == current_user.id
    )
    
    # Apply filters
    if mailbox_id:
        verify_mailbox_ownership(mailbox_id, current_user.id, db)
        query = query.filter(Subscription.mailbox_id == mailbox_id)
    
    if status_filter:
        # Convert status filter to boolean for is_active field
        if status_filter.lower() == 'active':
            query = query.filter(Subscription.is_active == True)
        elif status_filter.lower() == 'inactive':
            query = query.filter(Subscription.is_active == False)
    
    if category:
        query = query.filter(Subscription.category == category)
    
    # Get total count
    total = query.count()
    
    # Paginate
    subscriptions = query.order_by(Subscription.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return SubscriptionListResponse(
        subscriptions=[SubscriptionResponse.model_validate(s) for s in subscriptions],
        total=total,
        page=page,
        page_size=page_size,
        has_more=total > (page * page_size)
    )


@router.get("/stats", response_model=SubscriptionStats)
async def get_subscription_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get subscription statistics for the current user.
    
    Includes total costs, category breakdown, and upcoming renewals.
    """
    # Get all active subscriptions
    subscriptions = db.query(Subscription).join(Mailbox).filter(
        Mailbox.user_id == current_user.id,
        Subscription.is_active == True
    ).all()
    
    total_subscriptions = len(subscriptions)
    active_subscriptions = len([s for s in subscriptions if s.is_active])
    
    # Calculate costs
    monthly_cost = 0.0
    yearly_cost = 0.0
    
    for sub in subscriptions:
        if sub.amount and sub.billing_cycle:
            amount = float(sub.amount)
            if sub.billing_cycle == 'monthly':
                monthly_cost += amount
                yearly_cost += amount * 12
            elif sub.billing_cycle == 'yearly':
                yearly_cost += amount
                monthly_cost += amount / 12
            elif sub.billing_cycle == 'weekly':
                monthly_cost += amount * 4.33  # Average weeks per month
                yearly_cost += amount * 52
    
    # Category breakdown
    by_category = {}
    for sub in subscriptions:
        category = sub.category or 'other'
        if category not in by_category:
            by_category[category] = {'count': 0, 'total': 0.0}

        by_category[category]['count'] += 1

        # Calculate monthly cost for this subscription
        if sub.amount and sub.billing_cycle:
            amount = float(sub.amount)
            if sub.billing_cycle == 'monthly':
                by_category[category]['total'] += amount
            elif sub.billing_cycle == 'yearly':
                by_category[category]['total'] += amount / 12
            elif sub.billing_cycle == 'weekly':
                by_category[category]['total'] += amount * 4.33
    
    # Billing cycle breakdown
    by_billing_cycle = {}
    for sub in subscriptions:
        cycle = sub.billing_cycle or 'unknown'
        by_billing_cycle[cycle] = by_billing_cycle.get(cycle, 0) + 1
    
    # Upcoming renewals (next 30 days)
    today = datetime.now().date()
    thirty_days = today + timedelta(days=30)
    upcoming = [
        s for s in subscriptions
        if s.renewal_date and s.renewal_date <= thirty_days
    ]
    upcoming.sort(key=lambda x: x.renewal_date if x.renewal_date else datetime.max.date())
    
    return SubscriptionStats(
        total_subscriptions=total_subscriptions,
        active_subscriptions=active_subscriptions,
        total_monthly_cost=round(monthly_cost, 2),
        total_yearly_cost=round(yearly_cost, 2),
        by_category=by_category,
        by_billing_cycle=by_billing_cycle,
        upcoming_renewals=[SubscriptionResponse.model_validate(s) for s in upcoming[:5]]
    )


@router.get("/{subscription_id}", response_model=SubscriptionDetailResponse)
async def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific subscription by ID with detailed information including source emails.
    """
    # Query with eager loading of source emails
    subscription = db.query(Subscription).options(
        joinedload(Subscription.source_emails)
    ).join(Mailbox).filter(
        Subscription.id == subscription_id,
        Mailbox.user_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Build the detailed response with source emails and junction table data
    source_emails_data = []

    # Query the junction table to get extraction metadata
    for email in subscription.source_emails:
        # Get the junction table data
        junction_data = db.execute(
            subscription_emails.select().where(
                subscription_emails.c.subscription_id == subscription.id,
                subscription_emails.c.email_id == email.id
            )
        ).first()

        source_emails_data.append({
            'email': EmailMessageResponse.model_validate(email),
            'extraction_role': junction_data.extraction_role if junction_data else None,
            'extraction_data': junction_data.extraction_data if junction_data else None,
            'created_at': junction_data.created_at if junction_data else email.created_at
        })

    # Create the response model
    response_data = SubscriptionResponse.model_validate(subscription).model_dump()
    response_data['source_emails'] = source_emails_data

    return SubscriptionDetailResponse(**response_data)


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    update_data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update subscription details.
    
    Allows updating any subscription field.
    """
    subscription = db.query(Subscription).join(Mailbox).filter(
        Subscription.id == subscription_id,
        Mailbox.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
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
    current_user: User = Depends(get_current_user)
):
    """
    Delete a subscription.
    
    This removes the subscription record permanently.
    """
    subscription = db.query(Subscription).join(Mailbox).filter(
        Subscription.id == subscription_id,
        Mailbox.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    db.delete(subscription)
    db.commit()
    
    logger.info(f"Deleted subscription: {subscription_id}")
    return None
