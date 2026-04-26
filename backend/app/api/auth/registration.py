"""Registration and email-verification endpoints.

Exposes:

  - ``POST /register``               — create a new user (unverified) and
                                       dispatch a verification email.
  - ``POST /verify-email``           — verify the user's email with a
                                       token and auto-login (returns
                                       access + refresh tokens).
  - ``POST /resend-verification``    — re-send the verification email
                                       (rate-limited and IP-blocked).
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.auth._email_dispatch import (
    send_verification_email,
)
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    EmailVerificationRequest,
    EmailVerificationResponse,
    ResendVerificationRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
)
from app.security.email_verification import (
    EmailVerificationManager,
    VerificationRateLimiter,
)
from app.security.events import SecurityEventLogger
from app.security.jwt import create_access_token, create_refresh_token
from app.security.password import hash_password
from app.utils.config_helper import get_config_value

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register",
    response_model=EmailVerificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: UserRegister, request: Request, db: Session = Depends(get_db)
):
    """
    Register a new user and send email verification.

    Args:
        user_data: User registration data
        request: HTTP request for IP and user agent
        db: Database session

    Returns:
        Message indicating verification email sent

    Raises:
        HTTPException: If email already exists or verification fails
    """
    from app.models.invite_token import InviteToken

    # Get client info
    request.headers.get("user-agent")

    # Check invite token if required
    invite = None
    if settings.REQUIRE_INVITE_TOKEN:
        if not user_data.invite_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration requires an invite token. Please contact an administrator.",
            )

        invite = (
            db.query(InviteToken)
            .filter(InviteToken.token == user_data.invite_token)
            .first()
        )

        if not invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite token"
            )

        if not invite.is_valid:
            if invite.is_used:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This invite token has already been used",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This invite token has expired",
                )

        # Check if invite is for specific email
        if (
            invite.invited_email
            and invite.invited_email.lower() != user_data.email.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite is for a different email address",
            )

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        # If unverified account exists, block new registration
        if not existing_user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "An unverified account with this email already exists. "
                    "Please verify your email or request a new verification link."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Hash password
    password_hash, salt = hash_password(user_data.password)

    # Generate verification token
    verification_token = EmailVerificationManager.generate_verification_token()

    # Create new user (not verified yet)
    new_user = User(
        email=user_data.email,
        password_hash=password_hash,
        salt=salt,
        is_active=True,
        email_verified=False,
        email_verification_token=verification_token,
        email_verification_sent_at=datetime.utcnow(),
        display_name=user_data.display_name,
        settings={},
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Mark invite as used
    if invite:
        invite.is_used = True
        invite.used_by_id = new_user.id
        invite.used_at = datetime.utcnow()
        db.commit()

    logger.info(f"New user registered (unverified): {new_user.email}")

    # Send verification email
    frontend_url = get_config_value("frontend.url", settings.FRONTEND_URL, db)
    display_name = user_data.display_name or user_data.email.split("@")[0]
    send_verification_email(
        db,
        new_user,
        verification_token,
        frontend_url,
        display_name=display_name,
        failure_detail="Account created but failed to send verification email. Please try resending.",
    )

    return EmailVerificationResponse(
        message="Registration successful! Please check your email to verify your account.",
        email=new_user.email,
    )


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(
    verification_data: EmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Verify user's email address with token.

    Args:
        verification_data: Token from verification email
        request: HTTP request for IP tracking
        db: Database session

    Returns:
        Access and refresh tokens after successful verification

    Raises:
        HTTPException: If token is invalid, expired, or already used
    """
    # Get client info for brute force protection
    ip_address = request.client.host if request.client else None

    # Check if IP is blocked
    if ip_address:
        is_blocked, block_reason = VerificationRateLimiter.is_ip_blocked(db, ip_address)
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=block_reason
            )

    # Verify token
    success, user, error_message = EmailVerificationManager.verify_token(
        db, verification_data.token
    )

    if not success:
        # Track failed attempt for brute force protection
        if ip_address:
            block_error = VerificationRateLimiter.track_verification_attempt(
                db, ip_address
            )
            if block_error:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=block_error
                )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        )

    # Mark email as verified
    EmailVerificationManager.mark_as_verified(db, user)

    logger.info(f"Email verified successfully for user: {user.email}")

    # Log successful verification as security event
    SecurityEventLogger.log_successful_login(
        db=db,
        user_id=str(user.id),
        email=user.email,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )

    # Create tokens for automatic login
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/resend-verification", response_model=EmailVerificationResponse)
async def resend_verification(
    resend_data: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Resend email verification link.

    Args:
        resend_data: Email address to resend verification
        request: HTTP request for IP tracking
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If rate limit exceeded, email not found, or already verified
    """
    # Get client info
    ip_address = request.client.host if request.client else None

    # Check if IP is blocked
    if ip_address:
        is_blocked, block_reason = VerificationRateLimiter.is_ip_blocked(db, ip_address)
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=block_reason
            )

    # Check rate limit (12 per hour)
    allowed, rate_error = VerificationRateLimiter.check_rate_limit(resend_data.email)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=rate_error
        )

    # Find user by email
    user = db.query(User).filter(User.email == resend_data.email).first()

    if not user:
        # Don't reveal if email exists or not for security
        return EmailVerificationResponse(
            message=(
                "If an account with this email exists and is unverified, "
                "a verification email has been sent."
            ),
            email=resend_data.email,
        )

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified"
        )

    # Generate new verification token
    new_token = EmailVerificationManager.generate_verification_token()
    user.email_verification_token = new_token
    user.email_verification_sent_at = datetime.utcnow()
    db.commit()

    # Send verification email
    frontend_url = get_config_value("frontend.url", settings.FRONTEND_URL, db)
    display_name = user.display_name or user.email.split("@")[0]
    send_verification_email(
        db,
        user,
        new_token,
        frontend_url,
        display_name=display_name,
        failure_detail="Failed to send verification email. Please try again later.",
    )

    logger.info(f"Verification email resent to: {user.email}")

    return EmailVerificationResponse(
        message="Verification email sent! Please check your inbox.", email=user.email
    )
