"""
Private API-layer helpers for dispatching transactional emails from the
``app.api.auth`` package.

These helpers encapsulate the duplicated dispatch patterns that were
previously inlined in the monolithic ``api/auth.py``:

  - ``register``:                  send_verification_email
  - ``login`` (2FA email branch):  send_2fa_otp
  - ``2fa/setup`` (email method):  send_2fa_otp
  - ``resend-verification``:       send_verification_email

Each helper instantiates ``EmailService(db)`` internally, calls the
typed send method, and raises ``HTTPException(500)`` on failure —
matching the inline contract that previously existed.

Naming uses a leading underscore to signal these are private to the
``app.api.auth`` package and not intended as FastAPI dependencies.

Moved from ``app/api/_email_dispatch.py`` (Phase 4) into the auth
sub-package as part of C1 Phase 7, because ``api/auth/`` is the only
consumer.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


def build_verification_url(token: str, frontend_url: str) -> str:
    """
    Construct the email-verification URL for a given token.

    Parameters
    ----------
    token:
        The email verification token.
    frontend_url:
        Base URL of the frontend application (no trailing slash required).

    Returns
    -------
    str
        Full verification URL, e.g. ``https://app.example.com/verify-email/<token>``.
    """
    return f"{frontend_url}/verify-email/{token}"


def send_verification_email(
    db: Session,
    user: User,
    token: str,
    frontend_url: str,
    *,
    display_name: str | None = None,
    failure_detail: str = "Account created but failed to send verification email. Please try resending.",
) -> None:
    """
    Build the verification URL and dispatch a verification email.

    Parameters
    ----------
    db:
        Active SQLAlchemy session (passed to ``EmailService``).
    user:
        The user to send the email to.
    token:
        Email verification token.
    frontend_url:
        Base URL of the frontend application.
    display_name:
        Human-readable display name for the greeting.  If omitted,
        falls back to ``user.display_name`` or the email-address prefix.
    failure_detail:
        HTTP 500 detail message used when the send fails.

    Raises
    ------
    HTTPException
        ``HTTP 500`` if ``EmailService.send_email_verification`` returns
        ``success=False``.
    """
    resolved_name = (
        display_name or getattr(user, "display_name", None) or user.email.split("@")[0]
    )
    verification_url = build_verification_url(token, frontend_url)

    email_service = EmailService(db)
    success, error = email_service.send_email_verification(
        to_email=user.email,
        user_name=resolved_name,
        verification_url=verification_url,
    )

    if not success:
        logger.error(f"Failed to send verification email to {user.email}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=failure_detail,
        )


def send_2fa_otp(
    db: Session,
    user: User,
    otp_code: str,
    *,
    failure_detail: str = "Failed to send verification email",
) -> None:
    """
    Dispatch a two-factor authentication OTP email.

    Parameters
    ----------
    db:
        Active SQLAlchemy session (passed to ``EmailService``).
    user:
        The user to send the OTP to.
    otp_code:
        The generated OTP code string.
    failure_detail:
        HTTP 500 detail message used when the send fails.

    Raises
    ------
    HTTPException
        ``HTTP 500`` if ``EmailService.send_2fa_otp_email`` returns
        ``success=False``.
    """
    user_name = user.email.split("@")[0]

    email_service = EmailService(db)
    success, error = email_service.send_2fa_otp_email(
        to_email=user.email,
        user_name=user_name,
        otp_code=otp_code,
    )

    if not success:
        logger.error(f"Failed to send 2FA OTP email to {user.email}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=failure_detail,
        )
