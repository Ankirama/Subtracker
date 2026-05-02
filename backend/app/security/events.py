"""
Security event logging utility.
"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import logging

from app.models.admin import SecurityEvent

logger = logging.getLogger(__name__)


class SecurityEventLogger:
    """Utility for logging security events to the database."""

    # Event type constants
    FAILED_LOGIN = "failed_login"
    SUCCESSFUL_LOGIN = "successful_login"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    INVALID_TOKEN = "invalid_token"
    EXPIRED_TOKEN = "expired_token"
    ACCOUNT_LOCKED = "account_locked"
    PASSWORD_RESET = "password_reset"
    ADMIN_ACCESS = "admin_access"
    ADMIN_ACCESS_DENIED = "admin_access_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # Severity levels
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @staticmethod
    def log_event(
        db: Session,
        event_type: str,
        severity: str = LOW,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[SecurityEvent]:
        """
        Log a security event to the database.

        Args:
            db: Database session
            event_type: Type of security event (use constants)
            severity: Event severity (low, medium, high, critical)
            user_id: Optional user ID involved in the event
            ip_address: Optional IP address
            user_agent: Optional user agent string
            details: Optional additional details as dictionary

        Returns:
            Created SecurityEvent or None if failed
        """
        try:
            event = SecurityEvent(
                id=uuid.uuid4(),
                event_type=event_type,
                user_id=uuid.UUID(user_id) if user_id else None,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details or {},
                severity=severity,
                is_resolved=False,
                created_at=datetime.utcnow(),
            )

            db.add(event)
            db.commit()
            db.refresh(event)

            logger.info(
                f"Security event logged: {event_type} "
                f"(severity: {severity}, user_id: {user_id}, ip: {ip_address})"
            )

            return event

        except Exception as e:  # noqa: BLE001 — event logger must never raise
            logger.error(f"Failed to log security event: {str(e)}")
            db.rollback()
            return None

    @staticmethod
    def log_failed_login(
        db: Session,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: str = "invalid_credentials",
    ):
        """Log a failed login attempt."""
        return SecurityEventLogger.log_event(
            db=db,
            event_type=SecurityEventLogger.FAILED_LOGIN,
            severity=SecurityEventLogger.MEDIUM,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email, "reason": reason},
        )

    @staticmethod
    def log_successful_login(
        db: Session,
        user_id: str,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log a successful login."""
        return SecurityEventLogger.log_event(
            db=db,
            event_type=SecurityEventLogger.SUCCESSFUL_LOGIN,
            severity=SecurityEventLogger.LOW,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email},
        )

    @staticmethod
    def log_brute_force_attempt(
        db: Session,
        email: str,
        ip_address: Optional[str] = None,
        attempt_count: int = 0,
    ):
        """Log a brute force attack attempt."""
        return SecurityEventLogger.log_event(
            db=db,
            event_type=SecurityEventLogger.BRUTE_FORCE_ATTEMPT,
            severity=SecurityEventLogger.HIGH,
            ip_address=ip_address,
            details={"email": email, "attempt_count": attempt_count},
        )

    @staticmethod
    def log_unauthorized_access(
        db: Session,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        resource: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log an unauthorized access attempt."""
        return SecurityEventLogger.log_event(
            db=db,
            event_type=SecurityEventLogger.UNAUTHORIZED_ACCESS,
            severity=SecurityEventLogger.HIGH,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email, "resource": resource},
        )

    @staticmethod
    def log_invalid_token(
        db: Session,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Log an invalid token attempt."""
        return SecurityEventLogger.log_event(
            db=db,
            event_type=SecurityEventLogger.INVALID_TOKEN,
            severity=SecurityEventLogger.MEDIUM,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"error": error},
        )

    @staticmethod
    def log_admin_access(
        db: Session,
        user_id: str,
        email: str,
        resource: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log admin access to sensitive resources."""
        return SecurityEventLogger.log_event(
            db=db,
            event_type=SecurityEventLogger.ADMIN_ACCESS,
            severity=SecurityEventLogger.LOW,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email, "resource": resource},
        )

    @staticmethod
    def log_admin_access_denied(
        db: Session,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        resource: str = "",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: str = "insufficient_privileges",
    ):
        """Log denied admin access attempt."""
        return SecurityEventLogger.log_event(
            db=db,
            event_type=SecurityEventLogger.ADMIN_ACCESS_DENIED,
            severity=SecurityEventLogger.HIGH,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email, "resource": resource, "reason": reason},
        )


# In-memory store for tracking failed login attempts
# In production, use Redis or similar
_failed_login_attempts: Dict[str, list] = {}


def track_failed_login(email: str, ip_address: str) -> int:
    """
    Track failed login attempts by email and IP.

    Returns:
        Number of failed attempts in the last 15 minutes
    """
    key = f"{email}:{ip_address}"
    current_time = datetime.utcnow()

    if key not in _failed_login_attempts:
        _failed_login_attempts[key] = []

    # Add current attempt
    _failed_login_attempts[key].append(current_time)

    # Remove attempts older than 15 minutes
    cutoff_time = current_time.timestamp() - 900  # 15 minutes
    _failed_login_attempts[key] = [
        t for t in _failed_login_attempts[key] if t.timestamp() > cutoff_time
    ]

    return len(_failed_login_attempts[key])


def clear_failed_login_attempts(email: str, ip_address: str):
    """Clear failed login attempts after successful login."""
    key = f"{email}:{ip_address}"
    if key in _failed_login_attempts:
        del _failed_login_attempts[key]
