"""CRUD endpoints for subscriptions.

Handles: POST /, GET /, GET /{id}, PUT /{id}, DELETE /{id}.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.subscriptions._helpers import verify_mailbox_ownership
from app.database import get_db
from app.models.email_message import subscription_emails
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    EmailMessageResponse,
    SubscriptionCreate,
    SubscriptionDetailResponse,
    SubscriptionListResponse,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from app.security.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


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
