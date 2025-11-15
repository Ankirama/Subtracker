"""
SQLAlchemy model for subscriptions.
Placeholder for now - will be fully implemented in the next phase.
"""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Numeric, Date, ForeignKey, ARRAY, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Subscription(Base):
    """
    Subscription model representing a tracked subscription service.
    """
    __tablename__ = "subscriptions"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mailbox_id = Column(UUID(as_uuid=True), ForeignKey("mailboxes.id", ondelete="SET NULL"), nullable=True)

    # Core subscription data
    provider = Column(String(255), nullable=False, index=True)
    email_sender = Column(String(255), nullable=True)
    amount = Column(Numeric(10, 2), nullable=True)  # Nullable since AI extraction may not always find amount
    currency = Column(String(3), nullable=False, default='EUR')
    billing_cycle = Column(String(50), nullable=False)  # 'monthly', 'yearly', 'quarterly'

    renewal_date = Column(Date, nullable=True, index=True)
    next_billing_date = Column(Date, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Categorization
    category = Column(String(100), nullable=True, index=True)
    tags = Column(ARRAY(Text), nullable=True)

    # Custom differentiation field
    custom_label = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Tracking
    first_detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_confirmed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Processing metadata
    confidence_score = Column(Numeric(5, 2), nullable=True)  # 0.00 to 100.00
    extraction_method = Column(String(50), nullable=True)  # 'template', 'ai', 'manual'
    extraction_metadata = Column(JSONB, nullable=True)  # AI reasoning, field-level confidence, etc.

    # Payment processor metadata
    payment_processor = Column(JSONB, nullable=True)

    # Relationships
    user = relationship("User", backref="subscriptions")
    mailbox = relationship("Mailbox", back_populates="subscriptions")
    source_emails = relationship(
        "EmailMessage",
        secondary="subscription_emails",
        back_populates="subscriptions"
    )

    def __repr__(self):
        return f"<Subscription(id={self.id}, provider={self.provider}, amount={self.amount})>"
