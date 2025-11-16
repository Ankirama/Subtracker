"""
Notification API endpoints for managing user notifications and preferences.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.notification import Notification, NotificationPreference, NotificationType
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationPreferencesListResponse
)
from app.security.dependencies import get_current_user
from app.services.notification_service import NotificationService
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
    notification_type: Optional[NotificationType] = None
):
    """
    List notifications for the current user.

    Supports filtering by read/unread status and notification type.
    """
    # Build query
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )

    if unread_only:
        query = query.filter(Notification.is_read == False)

    if notification_type:
        query = query.filter(Notification.type == notification_type)

    # Get total count and unread count
    total = query.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()

    # Paginate
    notifications = query.order_by(Notification.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        has_more=total > (page * page_size)
    )


@router.get("/unread-count", response_model=dict)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """
    Mark specific notifications as read.
    """
    updated_count = NotificationService.mark_as_read(
        db,
        current_user.id,
        request.notification_ids
    )

    return {
        "success": True,
        "marked_read": updated_count
    }


@router.post("/mark-all-read", response_model=dict)
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark all unread notifications as read.
    """
    updated_count = NotificationService.mark_all_as_read(db, current_user.id)

    return {
        "success": True,
        "marked_read": updated_count
    }


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a notification.
    """
    deleted = NotificationService.delete_notification(
        db,
        current_user.id,
        notification_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    return None


@router.get("/preferences", response_model=NotificationPreferencesListResponse)
async def get_notification_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all notification preferences for the current user.

    If preferences don't exist, they will be created with default values.
    """
    # Initialize preferences if they don't exist
    NotificationService.init_user_preferences(db, current_user.id)

    # Get all preferences
    preferences = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id
    ).all()

    return NotificationPreferencesListResponse(
        preferences=[NotificationPreferenceResponse.model_validate(p) for p in preferences]
    )


@router.put("/preferences/{notification_type}", response_model=NotificationPreferenceResponse)
async def update_notification_preference(
    notification_type: NotificationType,
    update_data: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update notification preferences for a specific notification type.
    """
    # Get or create preference
    preference = NotificationService.get_or_create_preference(
        db,
        current_user.id,
        notification_type
    )

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(preference, field, value)

    db.commit()
    db.refresh(preference)

    logger.info(f"Updated notification preference for user {current_user.id}, type {notification_type}")
    return NotificationPreferenceResponse.model_validate(preference)
