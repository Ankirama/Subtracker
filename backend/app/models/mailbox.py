"""
SQLAlchemy model for mailboxes (email accounts).
"""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class Mailbox(Base):
    """
    Mailbox model representing a connected email account.

    Stores encrypted credentials for accessing email providers (JMAP, Gmail, Outlook).
    """
    __tablename__ = "mailboxes"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

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
    last_sync_status = Column(String(50), nullable=True)  # 'success', 'failed', 'in_progress', 'queued'
    last_sync_emails_processed = Column(Integer, nullable=True)
    last_sync_subscriptions_found = Column(Integer, nullable=True)
    last_sync_error_message = Column(Text, nullable=True)

    # Sync configuration
    sync_frequency = Column(String(50), default='weekly', nullable=False)  # 'manual', 'daily', 'weekly'
    batch_size = Column(Integer, default=100, nullable=False)
    import_date_filter = Column(String(50), nullable=True)  # 'all', '1year', '2years'

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="mailboxes")
    subscriptions = relationship("Subscription", back_populates="mailbox", cascade="all, delete-orphan")
    email_messages = relationship("EmailMessage", back_populates="mailbox", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'email_address', name='uq_user_email'),
    )

    def __repr__(self):
        return f"<Mailbox(id={self.id}, email={self.email_address}, provider={self.provider_type})>"
