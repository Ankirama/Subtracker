"""
SQLAlchemy model for tracking subscription price changes over time.
"""
from sqlalchemy import (
    Column, String, DateTime, Numeric, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class PriceHistory(Base):
    """
    Price history model for tracking subscription price changes.
    Records whenever a subscription's price changes.
    """
    __tablename__ = "price_history"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Price change details
    old_amount = Column(Numeric(10, 2), nullable=True)  # Previous price (null for first record)
    new_amount = Column(Numeric(10, 2), nullable=False)  # New price
    currency = Column(String(3), nullable=False, default='EUR')

    # Change metadata
    change_type = Column(String(50), nullable=False)  # 'increase', 'decrease', 'initial'
    change_percentage = Column(Numeric(5, 2), nullable=True)  # Percentage change (null for initial)

    # Detection info
    detected_from = Column(String(100), nullable=True)  # 'email', 'manual', 'api'
    notes = Column(Text, nullable=True)

    # Tracking
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    subscription = relationship("Subscription", backref="price_history")

    def __repr__(self):
        return f"<PriceHistory(id={self.id}, subscription_id={self.subscription_id}, change={self.old_amount} -> {self.new_amount})>"
