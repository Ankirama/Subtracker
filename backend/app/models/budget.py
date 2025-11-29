"""
SQLAlchemy model for budgets.
Tracks spending limits for subscriptions by category or overall.
"""

from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Budget(Base):
    """
    Budget model for tracking spending limits on subscriptions.
    Can be category-specific or overall budget.
    """

    __tablename__ = "budgets"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Budget configuration
    name = Column(
        String(255), nullable=False
    )  # e.g., "Entertainment Budget", "Overall Monthly Limit"
    category = Column(
        String(100), nullable=True, index=True
    )  # None means overall budget
    period = Column(
        String(50), nullable=False, default="monthly"
    )  # 'monthly', 'quarterly', 'yearly'

    # Financial limits
    limit_amount = Column(
        Numeric(10, 2), nullable=False
    )  # Budget limit in base currency
    currency = Column(String(3), nullable=False, default="EUR")

    # Alert configuration
    alert_threshold = Column(
        Integer, nullable=False, default=80
    )  # Percentage (0-100) when to alert
    alert_enabled = Column(
        String(20), nullable=False, default="true"
    )  # 'true' or 'false' as string

    # Tracking
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
    user = relationship("User", backref="budgets")

    def __repr__(self):
        return f"<Budget(id={self.id}, name={self.name}, category={self.category}, limit={self.limit_amount})>"
