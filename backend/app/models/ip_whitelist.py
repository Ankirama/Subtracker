"""
IP Whitelist Model

Model for storing whitelisted IP addresses that should never be blocked
by brute force protection or rate limiting.
"""

from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.sql import func
from app.database import Base


class IPWhitelist(Base):
    """Model for tracking whitelisted IP addresses."""

    __tablename__ = "ip_whitelist"

    ip_address = Column(String(45), primary_key=True)  # IPv6 max length
    description = Column(String(255), nullable=True)  # e.g., "Admin office IP"
    added_by_user_id = Column(String(36), nullable=False)  # Admin who added it
    added_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen = Column(
        DateTime(timezone=True), nullable=True
    )  # Last time this IP was used
    access_count = Column(
        Integer, default=0, nullable=False
    )  # Number of times IP was seen

    def __repr__(self):
        return f"<IPWhitelist {self.ip_address}>"
