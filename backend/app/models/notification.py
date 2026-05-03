"""
SQLAlchemy models for notifications system.

Supports both in-app notifications and email notifications with user preferences.
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum

from app.database import Base


class NotificationType(str, enum.Enum):
    """Types of notifications."""

    RENEWAL_REMINDER = "RENEWAL_REMINDER"
    TRIAL_ENDING = "TRIAL_ENDING"
    WEEKLY_SUMMARY = "WEEKLY_SUMMARY"
    MONTHLY_SUMMARY = "MONTHLY_SUMMARY"
    INACTIVE_SUBSCRIPTION = "INACTIVE_SUBSCRIPTION"
    PRICE_CHANGE = "PRICE_CHANGE"
    BUDGET_ALERT = "BUDGET_ALERT"
    SYSTEM_ANNOUNCEMENT = "SYSTEM_ANNOUNCEMENT"
    SYNC_SKIPPED_MANY = "SYNC_SKIPPED_MANY"
    SYNC_CIRCUIT_BREAKER = "SYNC_CIRCUIT_BREAKER"
    SYNC_PREVIEW_AVAILABLE = "SYNC_PREVIEW_AVAILABLE"
    CANCELLATION_DETECTED = "CANCELLATION_DETECTED"


class NotificationPriority(str, enum.Enum):
    """Priority levels for notifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Notification(Base):
    """
    Notification model for both in-app and email notifications.

    Stores notification history and tracks delivery status.
    """

    __tablename__ = "notifications"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Notification details
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    priority = Column(
        SQLEnum(NotificationPriority),
        nullable=False,
        default=NotificationPriority.MEDIUM,
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Optional link to related entity
    related_subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=True,
    )
    related_budget_id = Column(
        UUID(as_uuid=True), ForeignKey("budgets.id", ondelete="CASCADE"), nullable=True
    )

    # Additional data (e.g., spending amounts, subscription details)
    notification_metadata = Column(JSONB, nullable=True)

    # In-app notification tracking
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Email delivery tracking
    email_sent = Column(Boolean, default=False, nullable=False)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_error = Column(Text, nullable=True)  # Store email service errors if any

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at = Column(
        DateTime(timezone=True), nullable=True
    )  # Optional expiration for old notifications

    # Relationships
    user = relationship("User", backref="notifications")
    related_subscription = relationship("Subscription", backref="notifications")

    def __repr__(self):
        return f"<Notification(id={self.id}, type={self.type}, user_id={self.user_id})>"


class NotificationPreference(Base):
    """
    User preferences for notification delivery.

    Controls which notifications to receive and via which channels (in-app, email).
    """

    __tablename__ = "notification_preferences"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Notification type
    notification_type = Column(SQLEnum(NotificationType), nullable=False)

    # Channel preferences
    enabled = Column(Boolean, default=True, nullable=False)  # Master toggle
    in_app_enabled = Column(Boolean, default=True, nullable=False)
    email_enabled = Column(Boolean, default=True, nullable=False)

    # Type-specific settings
    # For renewal reminders: days before renewal to notify
    days_before_renewal = Column(Integer, nullable=True, default=3)

    # For summaries: which day of week (0=Monday, 6=Sunday) or day of month (1-31)
    summary_day_of_week = Column(Integer, nullable=True, default=0)  # Monday for weekly
    summary_day_of_month = Column(Integer, nullable=True, default=1)  # 1st for monthly

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", backref="notification_preferences")

    def __repr__(self):
        return f"<NotificationPreference(user_id={self.user_id}, type={self.notification_type})>"
