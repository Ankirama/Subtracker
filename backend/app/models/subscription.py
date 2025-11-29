"""
SQLAlchemy model for subscriptions.
Placeholder for now - will be fully implemented in the next phase.
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Numeric,
    Date,
    ForeignKey,
    ARRAY,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from dateutil.relativedelta import relativedelta
import uuid

from app.database import Base


class Subscription(Base):
    """
    Subscription model representing a tracked subscription service.
    """

    __tablename__ = "subscriptions"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mailbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mailboxes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Core subscription data
    provider = Column(String(255), nullable=False, index=True)
    email_sender = Column(String(255), nullable=True)
    amount = Column(
        Numeric(10, 2), nullable=True
    )  # Nullable since AI extraction may not always find amount
    currency = Column(String(3), nullable=False, default="EUR")
    billing_cycle = Column(
        String(50), nullable=False
    )  # 'monthly', 'yearly', 'quarterly'

    renewal_date = Column(Date, nullable=True, index=True)
    next_billing_date = Column(Date, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    manual_status_override = Column(
        Boolean, default=False, nullable=False
    )  # True if user manually changed is_active

    # Trial tracking
    trial_status = Column(
        String(50), nullable=True, index=True
    )  # 'none', 'trial', 'trial_ended', 'trial_cancelled', 'converted'
    trial_end_date = Column(Date, nullable=True)
    is_confirmed = Column(
        Boolean, default=True, nullable=False, index=True
    )  # True if 2+ emails OR no trial detected

    # Categorization
    category = Column(String(100), nullable=True, index=True)
    tags = Column(ARRAY(Text), nullable=True)

    # Custom differentiation field
    custom_label = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Cancellation tracking
    cancellation_status = Column(
        String(50), nullable=False, default="active", index=True
    )  # 'active', 'pending_cancellation', 'paused', 'cancelled'
    cancellation_requested_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_notes = Column(Text, nullable=True)

    # AI-suggested cancellation (requires user confirmation)
    suggested_cancellation_status = Column(
        String(50), nullable=True, index=True
    )  # Suggested status from AI
    cancellation_suggestion_reason = Column(
        Text, nullable=True
    )  # AI reasoning for the suggestion
    cancellation_suggestion_created_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When suggestion was made

    # Tracking
    first_detected_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_confirmed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Processing metadata
    confidence_score = Column(Numeric(5, 2), nullable=True)  # 0.00 to 100.00
    extraction_method = Column(String(50), nullable=True)  # 'template', 'ai', 'manual'
    extraction_metadata = Column(
        JSONB, nullable=True
    )  # AI reasoning, field-level confidence, etc.

    # Payment processor metadata
    payment_processor = Column(JSONB, nullable=True)

    # Relationships
    user = relationship("User", backref="subscriptions")
    mailbox = relationship("Mailbox", back_populates="subscriptions")
    source_emails = relationship(
        "EmailMessage", secondary="subscription_emails", back_populates="subscriptions"
    )

    @property
    def next_renewal_date(self):
        """
        Calculate the next future renewal date based on renewal_date and billing_cycle.

        If renewal_date is in the past, add billing cycles until it's in the future.
        If renewal_date is None, return None.

        Returns:
            date: Next future renewal date or None
        """
        if not self.renewal_date or not self.billing_cycle:
            return None

        today = datetime.now().date()
        next_date = self.renewal_date

        # If renewal date is already in the future, return it
        if next_date > today:
            return next_date

        # Map billing cycles to relativedelta parameters
        cycle_map = {
            "weekly": {"weeks": 1},
            "monthly": {"months": 1},
            "quarterly": {"months": 3},
            "biannual": {"months": 6},
            "yearly": {"years": 1},
            "annual": {"years": 1},
        }

        cycle_delta = cycle_map.get(self.billing_cycle.lower())
        if not cycle_delta:
            # Unknown billing cycle, return the stored date
            return next_date

        # Add billing cycles until date is in the future
        while next_date <= today:
            next_date = next_date + relativedelta(**cycle_delta)

        return next_date

    def __repr__(self):
        return f"<Subscription(id={self.id}, provider={self.provider}, amount={self.amount})>"
