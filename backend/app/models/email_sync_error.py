"""SQLAlchemy model for email sync error tracking.

Each row represents one email that could not be processed by the sync
pipeline (classification or persistence stage). The pipeline catches the
exception, classifies it, persists this row, and continues with the next
email — see services/sync_error_recorder.py.
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class EmailSyncError(Base):
    """Structured record of a single email that failed during sync pipeline processing.

    Created by SyncErrorRecorder after the per-email try/except catches any exception.
    Status lifecycle: pending → retried | resolved | ignored | auto_recovered.
    """

    __tablename__ = "email_sync_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mailboxes.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_history_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sync_history.id", ondelete="SET NULL"),
        nullable=True,
    )

    provider_message_id = Column(Text, nullable=True)
    subject = Column(Text, nullable=True)
    sender = Column(String(255), nullable=True)

    error_type = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    raw_payload = Column(JSONB, nullable=True)

    severity = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="pending")
    resolution = Column(String(50), nullable=True)

    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    __table_args__ = (
        Index("ix_email_sync_errors_mailbox_status", "mailbox_id", "status"),
        Index("ix_email_sync_errors_type_created", "error_type", "created_at"),
        Index("ix_email_sync_errors_created_at", "created_at"),
    )

    mailbox = relationship("Mailbox", back_populates="sync_errors")
    sync_history = relationship("SyncHistory", back_populates="errors")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])

    def __repr__(self):
        return (
            f"<EmailSyncError(id={self.id}, mailbox_id={self.mailbox_id}, "
            f"error_type={self.error_type}, status={self.status})>"
        )
