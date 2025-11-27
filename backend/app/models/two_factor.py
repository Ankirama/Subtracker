"""
Two-Factor Authentication models.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from datetime import datetime, timedelta
from app.database import Base


class EmailOTP(Base):
    """
    Temporary email OTP codes for two-factor authentication.
    Codes expire after 10 minutes.
    """

    __tablename__ = "email_otp"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code = Column(String(10), nullable=False)  # 6-digit code
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(
        String(1), default="N", nullable=False
    )  # 'Y' or 'N' (for simplicity)

    def __repr__(self):
        return f"<EmailOTP user_id={self.user_id} expires_at={self.expires_at}>"

    def is_expired(self) -> bool:
        """Check if the OTP code has expired."""
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the OTP code is valid (not expired and not used)."""
        return not self.is_expired() and self.is_used == "N"
