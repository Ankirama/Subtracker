"""Admin-related database models"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class AdminSetting(Base):
    """Admin configuration settings"""

    __tablename__ = "admin_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(JSONB, nullable=False)
    value_type = Column(String, nullable=False)  # 'string', 'number', 'boolean', 'json'
    is_secret = Column(Boolean, default=False, nullable=False)
    description = Column(Text)
    category = Column(String, index=True)  # 'api_keys', 'openai', 'email', 'features'
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class AdminAuditLog(Base):
    """Admin action audit trail"""

    __tablename__ = "admin_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String)
    resource_id = Column(String)
    details = Column(JSONB)
    ip_address = Column(String)
    user_agent = Column(String)
    severity = Column(String)  # 'info', 'warning', 'critical'
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )


class ApplicationLog(Base):
    """Application logs storage"""

    __tablename__ = "application_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level = Column(
        String, nullable=False, index=True
    )  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    logger_name = Column(String, index=True)
    message = Column(Text, nullable=False)
    module = Column(String)
    function_name = Column(String)
    line_number = Column(Integer)
    exception_type = Column(String)
    exception_message = Column(Text)
    stack_trace = Column(Text)
    context = Column(JSONB)
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )


class SecurityEvent(Base):
    """Security events tracking"""

    __tablename__ = "security_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(
        String, nullable=False, index=True
    )  # 'brute_force', 'suspicious_activity'
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    ip_address = Column(String)
    user_agent = Column(String)
    details = Column(JSONB)
    severity = Column(String, index=True)  # 'low', 'medium', 'high', 'critical'
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
