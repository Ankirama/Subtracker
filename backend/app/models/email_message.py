"""
SQLAlchemy models for email messages and subscription-email relationships.
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey,
    Text,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


# Junction table for many-to-many relationship
subscription_emails = Table(
    "subscription_emails",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column(
        "subscription_id",
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "email_id",
        UUID(as_uuid=True),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "extraction_role", String(50), nullable=True
    ),  # 'initial_detection', 'renewal', 'confirmation', etc.
    Column(
        "extraction_data", JSONB, nullable=True
    ),  # Specific data extracted from this email
    Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    ),
)


class EmailMessage(Base):
    """
    Email message model for storing emails that contain subscription information.
    """

    __tablename__ = "email_messages"

    # Primary key and foreign keys
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    mailbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mailboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Email identification (from email headers)
    message_id = Column(
        String(500), unique=True, nullable=False, index=True
    )  # Email Message-ID header
    thread_id = Column(String(500), nullable=True, index=True)  # Thread/conversation ID

    # Email content
    subject = Column(String(500), nullable=False)
    sender = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)
    recipient = Column(String(255), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    body_text = Column(Text, nullable=True)  # Plain text version
    body_html = Column(Text, nullable=True)  # HTML version

    # Email metadata
    labels = Column(JSONB, nullable=True)  # Email labels/folders
    attachments = Column(
        JSONB, nullable=True
    )  # Attachment metadata (filename, type, size)

    # Classification results
    is_subscription = Column(Boolean, default=False, nullable=False, index=True)
    classification_confidence = Column(Numeric(5, 2), nullable=True)  # 0.00 to 100.00
    classification_reasoning = Column(
        JSONB, nullable=True
    )  # AI reasoning for classification

    # Processing timestamps
    processed_at = Column(
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

    # Relationships
    mailbox = relationship("Mailbox", back_populates="email_messages")
    subscriptions = relationship(
        "Subscription", secondary=subscription_emails, back_populates="source_emails"
    )

    def __repr__(self):
        return f"<EmailMessage(id={self.id}, subject={self.subject}, sender={self.sender})>"
