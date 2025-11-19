from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.sql import func
from app.database import Base


class IPBlock(Base):
    """Model for tracking permanently blocked IP addresses"""
    __tablename__ = "ip_blocks"

    ip_address = Column(String(45), primary_key=True)  # IPv6 max length
    reason = Column(String(255), nullable=False)  # e.g., "email_verification_brute_force"
    blocked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    attempt_count = Column(Integer, nullable=False)  # Number of attempts that led to block

    def __repr__(self):
        return f"<IPBlock {self.ip_address}>"
