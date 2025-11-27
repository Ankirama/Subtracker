"""
User feedback model for cancellation research quality tracking.
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Float,
    Integer,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum


class FeedbackType(str, enum.Enum):
    """Types of feedback users can provide"""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    INACCURATE = "inaccurate"
    INCOMPLETE = "incomplete"
    WORKED = "worked"
    FAILED = "failed"


class CancellationFeedback(Base):
    """
    User feedback on cancellation research results.

    Tracks whether instructions were helpful, accurate, and successful.
    Used to measure AI prompt accuracy and identify providers needing updates.
    """

    __tablename__ = "cancellation_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Links to user and provider
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_cancellation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("provider_cancellation_info.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Feedback type and details
    feedback_type = Column(SQLEnum(FeedbackType), nullable=False)

    # Success tracking
    successfully_cancelled = Column(Boolean, nullable=True)  # True/False/None (unknown)
    time_taken_minutes = Column(Integer, nullable=True)  # How long it took

    # Ratings (1-5 scale)
    helpfulness_rating = Column(
        Integer, nullable=True
    )  # 1-5: How helpful were instructions?
    accuracy_rating = Column(
        Integer, nullable=True
    )  # 1-5: How accurate was the information?

    # Open-ended feedback
    comment = Column(Text, nullable=True)  # User's written feedback

    # Issues encountered (array of strings)
    issues_encountered = Column(JSONB, nullable=True)
    # Example: ["incorrect_url", "missing_steps", "outdated_info", "requires_phone"]

    # Context at time of feedback
    ai_confidence_at_feedback = Column(
        Float, nullable=True
    )  # AI confidence when user got instructions
    validation_quality_at_feedback = Column(
        Float, nullable=True
    )  # Validation quality score
    prompt_version_at_feedback = Column(
        String(50), nullable=True
    )  # Which prompt version was used

    # Metadata
    device_type = Column(String(50), nullable=True)  # "web", "mobile", "tablet"
    provider_name = Column(
        String(255), nullable=False, index=True
    )  # Denormalized for easy queries

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
    user = relationship("User", back_populates="cancellation_feedback")
    provider_cancellation = relationship(
        "ProviderCancellationInfo", back_populates="feedback"
    )

    def __repr__(self):
        return (
            f"<CancellationFeedback(id={self.id}, "
            f"provider={self.provider_name}, "
            f"type={self.feedback_type}, "
            f"successful={self.successfully_cancelled})>"
        )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "provider_cancellation_id": str(self.provider_cancellation_id),
            "provider_name": self.provider_name,
            "feedback_type": self.feedback_type.value if self.feedback_type else None,
            "successfully_cancelled": self.successfully_cancelled,
            "time_taken_minutes": self.time_taken_minutes,
            "helpfulness_rating": self.helpfulness_rating,
            "accuracy_rating": self.accuracy_rating,
            "comment": self.comment,
            "issues_encountered": self.issues_encountered,
            "ai_confidence_at_feedback": self.ai_confidence_at_feedback,
            "validation_quality_at_feedback": self.validation_quality_at_feedback,
            "prompt_version_at_feedback": self.prompt_version_at_feedback,
            "device_type": self.device_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
