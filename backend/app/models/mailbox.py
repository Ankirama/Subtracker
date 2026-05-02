"""
SQLAlchemy model for mailboxes (email accounts).
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base
from app.models.sync_history import SyncHistory


class Mailbox(Base):
    """
    Mailbox model representing a connected email account.

    Stores encrypted credentials for accessing email providers (JMAP, Gmail, Outlook).
    """

    __tablename__ = "mailboxes"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Provider configuration
    provider_type = Column(String(50), nullable=False)  # 'jmap', 'gmail', 'outlook'
    email_address = Column(String(255), nullable=False)

    # Encrypted credentials (using Fernet encryption from app.security.encryption)
    # Stores JSON with access tokens, refresh tokens, etc.
    encrypted_credentials = Column(Text, nullable=False)

    # Display settings
    display_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Sync status
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(
        String(50), nullable=True
    )  # 'success', 'failed', 'in_progress', 'queued'
    last_sync_emails_processed = Column(Integer, nullable=True)
    last_sync_subscriptions_found = Column(Integer, nullable=True)
    last_sync_error_message = Column(Text, nullable=True)
    last_sync_oldest_email_date = Column(DateTime(timezone=True), nullable=True)
    last_sync_newest_email_date = Column(DateTime(timezone=True), nullable=True)
    last_sync_new_emails_count = Column(Integer, nullable=True)
    last_sync_history_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "sync_history.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_mailboxes_last_sync_history_id",
        ),
        nullable=True,
    )

    # Sync resume capability (Issue #7)
    last_sync_started_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When current sync started
    last_sync_position = Column(
        Integer, nullable=True, default=0
    )  # Current position in pagination
    last_sync_batch_num = Column(
        Integer, nullable=True, default=0
    )  # Current batch number

    # User-initiated sync control (cancellation)
    sync_cancellation_requested = Column(
        Boolean, default=False, nullable=False
    )  # User requested to stop sync
    sync_cancelled_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When sync was cancelled by user

    # Real-time progress tracking (Issue #10)
    current_batch_number = Column(
        Integer, nullable=True
    )  # Current batch being processed
    total_batches_estimate = Column(Integer, nullable=True)  # Estimated total batches
    progress_percentage = Column(Float, nullable=True)  # Progress percentage (0-100)
    estimated_completion_time = Column(
        DateTime(timezone=True), nullable=True
    )  # Estimated completion time

    # OAuth reconnection tracking
    needs_reconnect = Column(
        Boolean, default=False, nullable=False
    )  # True if OAuth tokens expired and need re-authentication
    auth_error_at = Column(
        DateTime(timezone=True), nullable=True
    )  # When the auth error occurred
    auth_error_message = Column(
        String(500), nullable=True
    )  # Human-readable auth error message

    # Sync configuration
    sync_frequency = Column(
        String(50), default="weekly", nullable=False
    )  # 'manual', 'daily', 'weekly'
    batch_size = Column(Integer, default=100, nullable=False)
    import_date_filter = Column(String(50), nullable=True)  # 'all', '1year', '2years'

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
    user = relationship("User", back_populates="mailboxes")
    subscriptions = relationship(
        "Subscription", back_populates="mailbox", cascade="all, delete-orphan"
    )
    email_messages = relationship(
        "EmailMessage", back_populates="mailbox", cascade="all, delete-orphan"
    )
    sync_history = relationship(
        "SyncHistory",
        back_populates="mailbox",
        cascade="all, delete-orphan",
        foreign_keys=[SyncHistory.mailbox_id],
    )
    sync_errors = relationship(
        "EmailSyncError", back_populates="mailbox", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "email_address", name="uq_user_email"),
    )

    def __repr__(self):
        return f"<Mailbox(id={self.id}, email={self.email_address}, provider={self.provider_type})>"
