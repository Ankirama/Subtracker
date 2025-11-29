from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False, index=True)

    # Email Verification
    email_verified = Column(Boolean, default=False, nullable=False, index=True)
    email_verification_token = Column(
        String(255), nullable=True, unique=True, index=True
    )
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    display_name = Column(String(255), nullable=True)  # Optional personalized name

    # Two-Factor Authentication
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_method = Column(String(20), nullable=True)  # 'totp' or 'email'
    two_factor_secret = Column(String(255), nullable=True)  # Encrypted TOTP secret
    backup_codes = Column(JSON, default=[], nullable=False)  # Hashed backup codes

    # User settings stored as JSON
    settings = Column(JSON, default={}, nullable=False)

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
    mailboxes = relationship(
        "Mailbox", back_populates="user", cascade="all, delete-orphan"
    )
    cancellation_feedback = relationship(
        "CancellationFeedback", back_populates="user", cascade="all, delete-orphan"
    )
    push_subscriptions = relationship(
        "PushSubscription", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.email}>"
