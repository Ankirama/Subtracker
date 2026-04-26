"""Email transport — Resend wrapper.

Bare delivery layer extracted from the legacy ``services/email_service.py``
during the C1 Phase 5 consolidation. The old module is now a backward-compat
shim that re-exports :class:`EmailService` from this module.

The class still exposes two typed wrappers (``send_2fa_otp_email`` and
``send_email_verification``) because they are used by the
``api/_email_dispatch.py`` helper landed in Phase 4. The 3 typed wrappers
tied to the inline templates we migrated (``send_renewal_reminder``,
``send_weekly_summary``, ``send_monthly_summary``) have been removed —
``notification_service`` now calls ``EmailTemplates.generate_*`` +
``send_email`` directly.
"""

from __future__ import annotations

import logging
from typing import Optional

import resend
from sqlalchemy.orm import Session

from app.config import settings
from app.services.email.templates import EmailTemplates
from app.utils.config_helper import get_config_value

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Resend."""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize Resend client.

        Args:
            db: Optional database session to check admin settings
        """
        # Get config values (admin settings override env vars)
        api_key = get_config_value("resend.api_key", settings.RESEND_API_KEY, db)
        from_email = get_config_value(
            "resend.from_email", settings.RESEND_FROM_EMAIL, db
        )
        from_name = get_config_value("resend.from_name", settings.RESEND_FROM_NAME, db)

        # Configure Resend with API key
        resend.api_key = api_key

        # Store from email info
        self.from_email = from_email
        self.from_name = from_name

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Send an email via Resend.

        Returns (success: bool, error_message: Optional[str])
        """
        try:
            # Prepare email params
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            # Add plain text if provided
            if plain_content:
                params["text"] = plain_content

            # Send email via Resend
            email_response = resend.Emails.send(params)

            # Check if email was sent successfully
            if email_response and email_response.get("id"):
                logger.info(
                    f"Email sent successfully to {to_email}: {subject} (ID: {email_response['id']})"
                )
                return True, None
            else:
                error_msg = "Resend returned no email ID"
                logger.error(f"Failed to send email to {to_email}: {error_msg}")
                return False, error_msg

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Exception sending email to {to_email}: {error_msg}")
            return False, error_msg

    def send_2fa_otp_email(
        self,
        to_email: str,
        user_name: str,
        otp_code: str,
        expires_in_minutes: int = 10,
    ) -> tuple[bool, Optional[str]]:
        """
        Send 2FA OTP code email.

        Args:
            to_email: Recipient email address
            user_name: User's name
            otp_code: 6-digit OTP code
            expires_in_minutes: Code expiration time in minutes

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        subject = f"Your Two-Factor Authentication Code - {otp_code}"

        html_content = EmailTemplates.generate_2fa_otp_email(
            user_name=user_name,
            otp_code=otp_code,
            expires_in_minutes=expires_in_minutes,
        )

        plain_content = f"""
Hi {user_name},

You're receiving this email because someone attempted to log in to your Subscription Tracker account.

Your verification code is: {otp_code}

This code will expire in {expires_in_minutes} minutes.

SECURITY NOTICE:
If you didn't attempt to log in, please ignore this email and consider changing your password immediately.
Never share this code with anyone.

Subscription Tracker Team
        """.strip()

        return self.send_email(to_email, subject, html_content, plain_content)

    def send_email_verification(
        self, to_email: str, user_name: str, verification_url: str
    ) -> tuple[bool, Optional[str]]:
        """
        Send email verification email.

        Args:
            to_email: Recipient email address
            user_name: User's display name or email
            verification_url: Complete URL for email verification

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        subject = "Complete Your Registration - Subscription Tracker"

        html_content = EmailTemplates.generate_email_verification_email(
            user_name=user_name, verification_url=verification_url
        )

        plain_content = f"""
Hi {user_name}!

Thank you for signing up for Subscription Tracker!

To complete your registration and start managing your subscriptions, please verify your email address by clicking the link below:

{verification_url}

Important:
• This verification link expires in 24 hours
• The link can only be used once
• You won't be able to log in until you verify your email

If you didn't create an account, you can safely ignore this email.

Best regards,
Subscription Tracker Team
        """.strip()

        return self.send_email(to_email, subject, html_content, plain_content)
