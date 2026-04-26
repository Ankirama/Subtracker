"""Two-factor authentication endpoints.

Exposes:

  - ``POST /2fa/verify-login``                — complete login with a 2FA code.
  - ``POST /2fa/setup``                       — start 2FA setup (TOTP or email).
  - ``POST /2fa/enable``                      — confirm setup and enable 2FA.
  - ``POST /2fa/disable``                     — disable 2FA (password-confirmed).
  - ``GET  /2fa/status``                      — current 2FA status for user.
  - ``POST /2fa/backup-codes/regenerate``     — replace existing backup codes.

Per audit §A.3, this module imports **only** the ``TwoFactorAuth``
facade from ``app.security.two_factor``: the lower-level managers
(``TOTPManager``, ``EmailOTPManager``, ``BackupCodesManager``) must
never be imported here. All operations the API needs are exposed as
``TwoFactorAuth`` static methods.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.auth._email_dispatch import send_2fa_otp
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    BackupCodesRegenerateResponse,
    TokenResponse,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorEnableResponse,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
    TwoFactorVerifyRequest,
    UserResponse,
)
from app.security.dependencies import get_current_user
from app.security.events import SecurityEventLogger
from app.security.jwt import create_access_token, create_refresh_token
from app.security.password import verify_password
from app.security.two_factor import TwoFactorAuth

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/2fa/verify-login", response_model=TokenResponse)
async def verify_2fa_login(
    verify_data: TwoFactorVerifyRequest, request: Request, db: Session = Depends(get_db)
):
    """
    Verify 2FA code and complete login.

    Args:
        verify_data: 2FA verification request with email and code
        request: HTTP request for IP and user agent
        db: Database session

    Returns:
        Access token, refresh token, and user info

    Raises:
        HTTPException: If code is invalid or user not found
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Get user by email
    user = db.query(User).filter(User.email == verify_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    if not user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled for this account",
        )

    # Verify 2FA code
    is_valid = TwoFactorAuth.verify_two_factor(
        db=db,
        user=user,
        code=verify_data.code,
        is_backup_code=verify_data.is_backup_code,
    )

    if not is_valid:
        # Log failed 2FA attempt
        SecurityEventLogger.log_failed_login(
            db=db,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
            reason="invalid_2fa_code",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code"
        )

    logger.info(f"2FA verification successful for user: {user.email}")

    # Log successful login
    SecurityEventLogger.log_successful_login(
        db=db,
        user_id=str(user.id),
        email=user.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Create tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    setup_data: TwoFactorSetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initiate 2FA setup.

    For TOTP: Returns secret and QR code
    For Email: Sends OTP to user's email

    Args:
        setup_data: 2FA setup request with method
        current_user: Current authenticated user
        db: Database session

    Returns:
        Setup response with method-specific data
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled",
        )

    if setup_data.method == "totp":
        # Generate TOTP secret and QR code
        secret, qr_code = TwoFactorAuth.setup_totp(current_user)

        logger.info(f"TOTP setup initiated for user: {current_user.email}")

        return TwoFactorSetupResponse(
            method="totp",
            secret=secret,
            qr_code=qr_code,
            message="Scan the QR code with your authenticator app and enter the code to enable 2FA",
        )

    elif setup_data.method == "email":
        # Generate and send email OTP via the facade
        otp_code = TwoFactorAuth.create_email_otp(db, str(current_user.id))

        send_2fa_otp(db, current_user, otp_code)

        logger.info(f"Email OTP sent for 2FA setup to: {current_user.email}")

        return TwoFactorSetupResponse(
            method="email",
            message=f"Verification code sent to {current_user.email}. Enter the code to enable 2FA",
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA method. Must be 'totp' or 'email'",
        )


@router.post("/2fa/enable", response_model=TwoFactorEnableResponse)
async def enable_2fa(
    enable_data: TwoFactorEnableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Enable 2FA after verifying the code.

    Args:
        enable_data: 2FA enable request with verification code
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success response with backup codes
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled",
        )

    # The TOTP path additionally requires the freshly-generated secret
    # to be sent back from the client.
    if enable_data.method == "totp" and not enable_data.secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP secret is required",
        )

    if enable_data.method not in ("totp", "email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA method"
        )

    # Verify the code through the unified facade.
    is_valid = TwoFactorAuth.verify_setup_code(
        db=db,
        user=current_user,
        method=enable_data.method,
        code=enable_data.verification_code,
        secret=enable_data.secret,
    )

    if not is_valid:
        # Mirror the original error wording per method, since the
        # email-OTP message references expiration explicitly.
        detail = (
            "Invalid verification code"
            if enable_data.method == "totp"
            else "Invalid or expired verification code"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    backup_codes = TwoFactorAuth.enable_two_factor(
        db=db,
        user=current_user,
        method=enable_data.method,
        secret=enable_data.secret if enable_data.method == "totp" else None,
    )

    logger.info(
        f"{enable_data.method.upper()} 2FA enabled for user: {current_user.email}"
    )

    return TwoFactorEnableResponse(
        success=True,
        message="Two-factor authentication enabled successfully. Save your backup codes in a safe place.",
        backup_codes=backup_codes,
    )


@router.post("/2fa/disable")
async def disable_2fa(
    disable_data: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disable 2FA (requires password confirmation).

    Args:
        disable_data: Password for confirmation
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled",
        )

    # Verify password
    if not verify_password(disable_data.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password"
        )

    # Disable 2FA
    TwoFactorAuth.disable_two_factor(db, current_user)

    logger.info(f"2FA disabled for user: {current_user.email}")

    return {
        "success": True,
        "message": "Two-factor authentication disabled successfully",
    }


@router.get("/2fa/status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    """
    Get current 2FA status.

    Args:
        current_user: Current authenticated user

    Returns:
        2FA status
    """
    return TwoFactorStatusResponse(
        enabled=current_user.two_factor_enabled,
        method=current_user.two_factor_method,
        backup_codes_remaining=(
            len(current_user.backup_codes) if current_user.backup_codes else 0
        ),
    )


@router.post(
    "/2fa/backup-codes/regenerate", response_model=BackupCodesRegenerateResponse
)
async def regenerate_backup_codes(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Regenerate backup codes (replaces old ones).

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        New backup codes
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled",
        )

    # Replace stored codes via the facade.
    new_codes = TwoFactorAuth.regenerate_backup_codes(db, current_user)

    logger.info(f"Backup codes regenerated for user: {current_user.email}")

    return BackupCodesRegenerateResponse(
        success=True,
        message="Backup codes regenerated successfully. Save them in a safe place.",
        backup_codes=new_codes,
    )
