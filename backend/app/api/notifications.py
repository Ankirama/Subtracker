"""
Notification API endpoints for managing user notifications and preferences.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
from uuid import UUID
from datetime import date, timedelta

from app.database import get_db
from app.models.user import User
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
)
from app.models.subscription import Subscription
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationPreferencesListResponse,
)
from app.security.dependencies import get_current_user
from app.services.notification_service import NotificationService
from app.services.summary_service import SummaryService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: Optional[NotificationType] = None,
):
    """
    List notifications for the current user.

    Supports filtering by read/unread status and notification type.
    """
    # Build query
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if unread_only:
        query = query.filter(not Notification.is_read)

    if notification_type:
        query = query.filter(Notification.type == notification_type)

    # Get total count and unread count
    total = query.count()
    unread_count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, not Notification.is_read)
        .count()
    )

    # Paginate
    notifications = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        has_more=total > (page * page_size),
    )


@router.get("/unread-count", response_model=dict)
async def get_unread_count(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get the count of unread notifications.

    Useful for displaying badge count on notification bell.
    """
    count = NotificationService.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.post("/mark-read", response_model=dict)
async def mark_notifications_read(
    request: NotificationMarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark specific notifications as read.
    """
    updated_count = NotificationService.mark_as_read(
        db, current_user.id, request.notification_ids
    )

    return {"success": True, "marked_read": updated_count}


@router.post("/mark-all-read", response_model=dict)
async def mark_all_notifications_read(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Mark all unread notifications as read.
    """
    updated_count = NotificationService.mark_all_as_read(db, current_user.id)

    return {"success": True, "marked_read": updated_count}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a notification.
    """
    deleted = NotificationService.delete_notification(
        db, current_user.id, notification_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )

    return None


@router.get("/preferences", response_model=NotificationPreferencesListResponse)
async def get_notification_preferences(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get all notification preferences for the current user.

    If preferences don't exist, they will be created with default values.
    """
    # Initialize preferences if they don't exist
    NotificationService.init_user_preferences(db, current_user.id)

    # Get all preferences
    preferences = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == current_user.id)
        .all()
    )

    return NotificationPreferencesListResponse(
        preferences=[
            NotificationPreferenceResponse.model_validate(p) for p in preferences
        ]
    )


@router.put(
    "/preferences/{notification_type}", response_model=NotificationPreferenceResponse
)
async def update_notification_preference(
    notification_type: NotificationType,
    update_data: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update notification preferences for a specific notification type.
    """
    # Get or create preference
    preference = NotificationService.get_or_create_preference(
        db, current_user.id, notification_type
    )

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(preference, field, value)

    db.commit()
    db.refresh(preference)

    logger.info(
        f"Updated notification preference for user {current_user.id}, type {notification_type}"
    )
    return NotificationPreferenceResponse.model_validate(preference)


@router.get("/upcoming-renewals", response_model=List[dict])
async def get_upcoming_renewals(
    days_ahead: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get upcoming subscription renewals.

    Args:
        days_ahead: Number of days ahead to check (default 30, max 90)

    Returns:
        List of subscriptions with upcoming renewals
    """
    today = date.today()
    future_date = today + timedelta(days=days_ahead)

    subscriptions = (
        db.query(Subscription)
        .filter(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.is_active,
                or_(
                    and_(
                        Subscription.next_billing_date.isnot(None),
                        Subscription.next_billing_date >= today,
                        Subscription.next_billing_date <= future_date,
                    ),
                    and_(
                        Subscription.renewal_date.isnot(None),
                        Subscription.renewal_date >= today,
                        Subscription.renewal_date <= future_date,
                    ),
                ),
            )
        )
        .order_by(Subscription.next_billing_date, Subscription.renewal_date)
        .all()
    )

    # Calculate days until renewal for each
    result = []
    for sub in subscriptions:
        renewal_date = sub.next_billing_date or sub.renewal_date
        if renewal_date:
            days_until = (renewal_date - today).days
            result.append(
                {
                    "subscription_id": str(sub.id),
                    "provider": sub.provider,
                    "amount": float(sub.amount) if sub.amount else 0,
                    "currency": sub.currency,
                    "billing_cycle": sub.billing_cycle,
                    "renewal_date": renewal_date.isoformat(),
                    "days_until_renewal": days_until,
                }
            )

    logger.info(f"Found {len(result)} upcoming renewals for user {current_user.id}")
    return result


@router.get("/summary/preview", response_model=dict)
async def preview_summary(
    period_type: str = Query("weekly", pattern="^(weekly|monthly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview a subscription summary (weekly or monthly).

    Args:
        period_type: Type of summary to preview ('weekly' or 'monthly')

    Returns:
        Summary data that would be sent in the email
    """
    try:
        if period_type == "weekly":
            summary_data = SummaryService.generate_weekly_summary(db, current_user)
        else:
            summary_data = SummaryService.generate_monthly_summary(db, current_user)

        logger.info(
            f"Generated {period_type} summary preview for user {current_user.id}"
        )
        return summary_data

    except Exception as e:
        logger.error(
            f"Failed to generate summary preview for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary preview: {str(e)}",
        )
