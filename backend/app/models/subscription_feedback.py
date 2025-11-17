"""
SQLAlchemy model for subscription feedback.
Stores user feedback on AI-detected subscriptions to improve classification.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class SubscriptionFeedback(Base):
    """
    Stores user feedback when rejecting AI-detected subscriptions.
    Used to improve future AI classification accuracy.
    """
    __tablename__ = "subscription_feedback"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), nullable=False)  # Not FK - subscription may be deleted

    # Feedback details
    feedback_type = Column(String(50), nullable=False, index=True)  # Maps to feedback_type enum
    feedback_text = Column(Text, nullable=True)  # Optional additional explanation

    # Snapshot of subscription data for analysis
    subscription_snapshot = Column(JSONB, nullable=False)  # Full subscription data before deletion

    # AI classification data that led to this detection
    ai_classification_data = Column(JSONB, nullable=True)  # AI reasoning and confidence scores

    # Related emails that caused the misclassification
    source_email_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=[])

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", backref="subscription_feedback")

    def __repr__(self):
        return f"<SubscriptionFeedback(id={self.id}, type={self.feedback_type}, subscription={self.subscription_id})>"
