"""
Email filtering service to prevent processing system-generated emails.

Prevents the system from parsing its own notification emails as subscriptions.
"""

from typing import Optional
from sqlalchemy.orm import Session
import logging

from app.config import settings
from app.utils.config_helper import get_config_value
from app.email_providers.base import EmailMessage

logger = logging.getLogger(__name__)


def is_system_email(email: EmailMessage, db: Optional[Session] = None) -> bool:
    """
    Check if an email is from the system itself (to prevent self-parsing).

    Args:
        email: Email message to check
        db: Optional database session to check admin settings

    Returns:
        True if this is a system-generated email that should be ignored
    """
    # Get configured system email addresses
    system_from_email = get_config_value(
        "resend.from_email", settings.RESEND_FROM_EMAIL, db
    )

    # Check if sender matches system email
    if email.sender and system_from_email:
        sender_lower = email.sender.lower().strip()
        system_lower = system_from_email.lower().strip()

        if sender_lower == system_lower:
            logger.info(
                f"Filtering out system email from {email.sender}: {email.subject}"
            )
            return True

    # Check for system email indicators in subject (additional safety)
    if email.subject:
        system_subject_patterns = [
            "Subscription Tracker",  # Our system name
            "Trial Ends Tomorrow",  # Our trial reminder format
            "Trial Ending Soon",  # Our trial reminder format
            "Reminder:",  # Our renewal reminder format
            "Budget Alert",  # Our budget alert format
            "Weekly Summary",  # Our summary format
            "Monthly Summary",  # Our summary format
        ]

        for pattern in system_subject_patterns:
            if pattern in email.subject:
                logger.info(
                    f"Filtering out system email by subject pattern '{pattern}': {email.subject}"
                )
                return True

    # Check for system email indicators in sender name
    if email.sender_name:
        system_sender_patterns = [
            "Subscription Tracker",
            "SubTracker",
        ]

        for pattern in system_sender_patterns:
            if pattern in email.sender_name:
                logger.info(
                    f"Filtering out system email by sender name '{pattern}': {email.sender_name}"
                )
                return True

    return False


def should_process_email(email: EmailMessage, db: Optional[Session] = None) -> bool:
    """
    Determine if an email should be processed for subscription detection.

    Args:
        email: Email message to check
        db: Optional database session

    Returns:
        True if email should be processed, False if it should be skipped
    """
    # Filter out system emails
    if is_system_email(email, db):
        return False

    # Add other filtering rules here as needed
    # For example:
    # - Spam detection
    # - Out-of-office replies
    # - Delivery reports
    # - Automated replies

    return True
