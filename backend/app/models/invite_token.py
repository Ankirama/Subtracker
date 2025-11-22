"""
Invite Token model for invite-only registration.
"""
import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class InviteToken(Base):
    """
    Model for managing invite tokens for user registration.
    Only admins can create invite tokens.
    """
    __tablename__ = "invite_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(64), unique=True, nullable=False, index=True)

    # Who created this invite
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_invites")

    # Optional: pre-fill email for the invite
    invited_email = Column(String(255), nullable=True)

    # Invite metadata
    note = Column(Text, nullable=True)  # Admin note about who this is for

    # Usage tracking
    is_used = Column(Boolean, default=False, nullable=False)
    used_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    used_by = relationship("User", foreign_keys=[used_by_id], backref="used_invite")
    used_at = Column(DateTime, nullable=True)

    # Expiration
    expires_at = Column(DateTime, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_valid(self) -> bool:
        """Check if invite token is still valid (not used and not expired)."""
        return not self.is_used and datetime.utcnow() < self.expires_at

    @classmethod
    def generate_token(cls) -> str:
        """Generate a secure random token."""
        import secrets
        return secrets.token_urlsafe(32)

    @classmethod
    def create_invite(
        cls,
        created_by_id: uuid.UUID,
        invited_email: str = None,
        note: str = None,
        expires_in_days: int = 7
    ) -> "InviteToken":
        """Create a new invite token."""
        return cls(
            token=cls.generate_token(),
            created_by_id=created_by_id,
            invited_email=invited_email,
            note=note,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
        )
