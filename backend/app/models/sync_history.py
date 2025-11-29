"""
SQLAlchemy model for sync history tracking.
Maintains historical records of all email synchronization operations.
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    Text,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class SyncHistory(Base):
    """
    SyncHistory model for tracking email synchronization operations.

    Provides complete audit trail and historical analysis of sync operations.
    """

    __tablename__ = "sync_history"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    mailbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mailboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timing information
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Status tracking
    status = Column(
        String(50), nullable=False, index=True
    )  # 'completed', 'failed', 'cancelled', 'in_progress'

    # Sync metrics
    total_emails_processed = Column(Integer, default=0, nullable=False)
    subscriptions_found = Column(Integer, default=0, nullable=False)
    subscriptions_updated = Column(Integer, default=0, nullable=False)
    batches_processed = Column(Integer, default=0, nullable=False)

    # Sync configuration
    sync_type = Column(String(50), nullable=True)  # 'full', 'incremental', 'manual'
    date_filter_used = Column(
        String(50), nullable=True
    )  # 'all', '1year', '2years', etc.
    batch_size_used = Column(Integer, nullable=True)

    # Resume tracking
    was_resumed = Column(Boolean, default=False, nullable=False)
    resumed_from_position = Column(Integer, nullable=True)
    resumed_from_batch = Column(Integer, nullable=True)

    # Error information
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)

    # Progress snapshot (final values)
    final_position = Column(Integer, nullable=True)
    final_batch_number = Column(Integer, nullable=True)
    final_progress_percentage = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    mailbox = relationship("Mailbox", back_populates="sync_history")

    def __repr__(self):
        return f"<SyncHistory(id={self.id}, mailbox_id={self.mailbox_id}, status={self.status}, started={self.started_at})>"
