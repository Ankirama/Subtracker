"""
Pydantic schemas for notification endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

from app.models.notification import NotificationType, NotificationPriority


class NotificationResponse(BaseModel):
    """Schema for notification response."""
    id: UUID
    user_id: UUID
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    related_subscription_id: Optional[UUID] = None
    notification_metadata: Optional[dict] = None
    is_read: bool
    read_at: Optional[datetime] = None
    email_sent: bool
    email_sent_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list."""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    has_more: bool


class NotificationMarkReadRequest(BaseModel):
    """Schema for marking notifications as read."""
    notification_ids: list[UUID] = Field(..., min_length=1, description="List of notification IDs to mark as read")


class NotificationPreferenceResponse(BaseModel):
    """Schema for notification preference response."""
    id: UUID
    user_id: UUID
    notification_type: NotificationType
    enabled: bool
    in_app_enabled: bool
    email_enabled: bool
    days_before_renewal: Optional[int] = None
    summary_day_of_week: Optional[int] = None
    summary_day_of_month: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating notification preferences."""
    enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    days_before_renewal: Optional[int] = Field(None, ge=0, le=30, description="Days before renewal (0-30)")
    summary_day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    summary_day_of_month: Optional[int] = Field(None, ge=1, le=31, description="Day of month (1-31)")


class NotificationPreferencesListResponse(BaseModel):
    """Schema for list of notification preferences."""
    preferences: list[NotificationPreferenceResponse]
