"""
Authentication API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    TwoFactorRequiredResponse,
    RefreshTokenRequest,
    UserResponse,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorEnableRequest,
    TwoFactorEnableResponse,
    TwoFactorDisableRequest,
    TwoFactorVerifyRequest,
    TwoFactorStatusResponse,
    BackupCodesRegenerateResponse,
    EmailVerificationResponse,
    EmailVerificationRequest,
    ResendVerificationRequest,
    ProfileUpdateRequest,
    PasswordChangeRequest,
    UserPreferencesUpdate,
    DeleteAccountRequest,
)
from app.security.password import hash_password, verify_password
from app.security.jwt import create_access_token, create_refresh_token, verify_token
from app.security.dependencies import get_current_user
from app.security.events import (
    SecurityEventLogger,
    track_failed_login,
    clear_failed_login_attempts,
)
from app.security.two_factor import (
    TwoFactorAuth,
    TOTPManager,
    EmailOTPManager,
    BackupCodesManager,
)
from app.services.email_service import EmailService
from app.security.email_verification import (
    EmailVerificationManager,
    VerificationRateLimiter,
)
from app.config import settings
from app.utils.config_helper import get_config_value
from datetime import datetime
import logging

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
                detail="An unverified account with this email already exists. Please verify your email or request a new verification link.",
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

    # Build verification URL
    frontend_url = get_config_value("frontend.url", settings.FRONTEND_URL, db)
    verification_url = f"{frontend_url}/verify-email/{verification_token}"

    # Send verification email
    email_service = EmailService(db)
    display_name = user_data.display_name or user_data.email.split("@")[0]
    success, error = email_service.send_email_verification(
        to_email=new_user.email,
        user_name=display_name,
        verification_url=verification_url,
    )

    if not success:
        logger.error(f"Failed to send verification email to {new_user.email}: {error}")
        # Don't fail registration, user can request resend
        # But log the issue
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account created but failed to send verification email. Please try resending.",
        )

    return EmailVerificationResponse(
        message="Registration successful! Please check your email to verify your account.",
        email=new_user.email,
    )


@router.post("/login")
async def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    """
    Login user and return JWT tokens or 2FA challenge.

    Args:
        user_data: User login credentials
        request: HTTP request for IP and user agent
        db: Database session

    Returns:
        TokenResponse if no 2FA, TwoFactorRequiredResponse if 2FA enabled

    Raises:
        HTTPException: If credentials are invalid or account locked
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Check for brute force attempts
    if ip_address:
        failed_attempts = track_failed_login(user_data.email, ip_address)

        # Block after 5 failed attempts in 15 minutes
        if failed_attempts >= 5:
            # Log brute force attempt
            SecurityEventLogger.log_brute_force_attempt(
                db=db,
                email=user_data.email,
                ip_address=ip_address,
                attempt_count=failed_attempts,
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
            )

    # Get user by email
    user = db.query(User).filter(User.email == user_data.email).first()

    # Verify user exists and password is correct
    if not user or not verify_password(user_data.password, user.password_hash):
        # Log failed login attempt
        SecurityEventLogger.log_failed_login(
            db=db,
            email=user_data.email,
            ip_address=ip_address,
            user_agent=user_agent,
            reason="invalid_credentials",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if email is verified
    if not user.email_verified:
        # Log failed login for unverified email
        SecurityEventLogger.log_failed_login(
            db=db,
            email=user_data.email,
            ip_address=ip_address,
            user_agent=user_agent,
            reason="email_not_verified",
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email before logging in.",
        )

    # Check if user is active
    if not user.is_active:
        # Log failed login for inactive account
        SecurityEventLogger.log_failed_login(
            db=db,
            email=user_data.email,
            ip_address=ip_address,
            user_agent=user_agent,
            reason="account_inactive",
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    # Clear failed login attempts on successful password verification
    if ip_address:
        clear_failed_login_attempts(user_data.email, ip_address)

    # Check if 2FA is enabled
    if user.two_factor_enabled:
        logger.info(f"2FA required for user: {user.email}")

        # If email method, send OTP code
        if user.two_factor_method == "email":
            otp_code = EmailOTPManager.create_otp(db, str(user.id))

            # Send email
            email_service = EmailService(db)
            success, error = email_service.send_2fa_otp_email(
                to_email=user.email,
                user_name=user.email.split("@")[0],
                otp_code=otp_code,
            )

            if not success:
                logger.error(f"Failed to send 2FA OTP email to {user.email}: {error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send verification email",
                )

            return TwoFactorRequiredResponse(
                requires_2fa=True,
                method="email",
                message=f"Verification code sent to {user.email}. Please enter the code to complete login.",
            )
        else:  # totp
            return TwoFactorRequiredResponse(
                requires_2fa=True,
                method="totp",
                message="Enter the verification code from your authenticator app to complete login.",
            )

    # No 2FA - proceed with normal login
    logger.info(f"User logged in: {user.email}")

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


@router.post("/refresh", response_model=dict)
async def refresh_access_token(
    token_data: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Args:
        token_data: Refresh token
        request: HTTP request for IP and user agent
        db: Database session

    Returns:
        New access token

    Raises:
        HTTPException: If refresh token is invalid
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        # Verify refresh token
        payload = verify_token(token_data.refresh_token)

        # Check token type
        if payload.get("type") != "refresh":
            # Log invalid token type
            SecurityEventLogger.log_invalid_token(
                db=db,
                ip_address=ip_address,
                user_agent=user_agent,
                error="invalid_token_type",
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        user_id = payload.get("user_id")
        if not user_id:
            # Log invalid token payload
            SecurityEventLogger.log_invalid_token(
                db=db,
                ip_address=ip_address,
                user_agent=user_agent,
                error="invalid_token_payload",
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        # Verify user still exists and is active
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            # Log token use for inactive/deleted user
            SecurityEventLogger.log_invalid_token(
                db=db,
                ip_address=ip_address,
                user_agent=user_agent,
                error="user_not_found_or_inactive",
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Create new access token
        access_token = create_access_token(user_id)

        logger.info(f"Access token refreshed for user: {user.email}")

        return {"access_token": access_token, "token_type": "bearer"}

    except JWTError as e:
        # Log JWT verification failure
        SecurityEventLogger.log_invalid_token(
            db=db,
            ip_address=ip_address,
            user_agent=user_agent,
            error=f"jwt_error: {str(e)}",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user (from dependency)

    Returns:
        User information
    """
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user (client-side should delete tokens).

    Args:
        current_user: Current authenticated user

    Returns:
        Success message

    Note:
        JWT tokens are stateless, so logout is handled client-side by deleting tokens.
        This endpoint is mainly for logging and future token blacklisting if needed.
    """
    logger.info(f"User logged out: {current_user.email}")

    return {"message": "Successfully logged out"}


# Account Management Endpoints


@router.put("/me/profile", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user profile (display_name, email).

    Args:
        profile_data: Profile update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user information
    """
    # Update display_name if provided
    if profile_data.display_name is not None:
        current_user.display_name = profile_data.display_name

    # Update email if provided and different
    if profile_data.email and profile_data.email != current_user.email:
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == profile_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        current_user.email = profile_data.email
        current_user.email_verified = False  # Re-verify new email

    db.commit()
    db.refresh(current_user)

    logger.info(f"Profile updated for user: {current_user.email}")
    return UserResponse.model_validate(current_user)


@router.put("/me/password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user password.

    Args:
        password_data: Password change data with current and new password
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Hash new password
    new_hash, new_salt = hash_password(password_data.new_password)
    current_user.password_hash = new_hash
    current_user.salt = new_salt

    db.commit()

    logger.info(f"Password changed for user: {current_user.email}")
    return {"message": "Password changed successfully"}


@router.put("/me/preferences")
async def update_preferences(
    preferences_data: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user preferences (theme, language, currency, etc.).

    Args:
        preferences_data: User preferences update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated preferences
    """
    # Get current settings or initialize empty dict
    settings = current_user.settings if isinstance(current_user.settings, dict) else {}

    # Update preferences
    if preferences_data.theme is not None:
        settings["theme"] = preferences_data.theme
    if preferences_data.language is not None:
        settings["language"] = preferences_data.language
    if preferences_data.currency is not None:
        settings["currency"] = preferences_data.currency
    if preferences_data.date_format is not None:
        settings["date_format"] = preferences_data.date_format
    if preferences_data.timezone is not None:
        settings["timezone"] = preferences_data.timezone

    current_user.settings = settings
    db.commit()
    db.refresh(current_user)

    logger.info(f"Preferences updated for user: {current_user.email}")
    return {"message": "Preferences updated successfully", "preferences": settings}


@router.delete("/me")
async def delete_account(
    delete_data: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete user account (requires password confirmation).

    Args:
        delete_data: Account deletion request with password
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    from app.security.password import verify_password

    # Verify password
    if not verify_password(delete_data.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password is incorrect"
        )

    # Verify confirmation
    if not delete_data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account deletion not confirmed",
        )

    email = current_user.email
    db.delete(current_user)
    db.commit()

    logger.info(f"Account deleted for user: {email}")
    return {"message": "Account deleted successfully"}


# Two-Factor Authentication Endpoints


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
        # Generate and send email OTP
        otp_code = EmailOTPManager.create_otp(db, str(current_user.id))

        # Send email
        email_service = EmailService(db)
        success, error = email_service.send_2fa_otp_email(
            to_email=current_user.email,
            user_name=current_user.email.split("@")[0],
            otp_code=otp_code,
        )

        if not success:
            logger.error(
                f"Failed to send 2FA OTP email to {current_user.email}: {error}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email",
            )

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

    # Verify the code based on method
    if enable_data.method == "totp":
        if not enable_data.secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP secret is required",
            )

        # Verify TOTP code
        is_valid = TOTPManager.verify_code(
            enable_data.secret, enable_data.verification_code
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code",
            )

        # Enable 2FA with TOTP
        backup_codes = TwoFactorAuth.enable_two_factor(
            db=db, user=current_user, method="totp", secret=enable_data.secret
        )

        logger.info(f"TOTP 2FA enabled for user: {current_user.email}")

    elif enable_data.method == "email":
        # Verify Email OTP
        is_valid = EmailOTPManager.verify_code(
            db, str(current_user.id), enable_data.verification_code
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )

        # Enable 2FA with Email
        backup_codes = TwoFactorAuth.enable_two_factor(
            db=db, user=current_user, method="email", secret=None
        )

        logger.info(f"Email 2FA enabled for user: {current_user.email}")

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA method"
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

    # Generate new backup codes
    new_codes = BackupCodesManager.generate_codes()
    hashed_codes = BackupCodesManager.hash_codes(new_codes)

    # Update user's backup codes
    current_user.backup_codes = hashed_codes
    db.commit()

    logger.info(f"Backup codes regenerated for user: {current_user.email}")

    return BackupCodesRegenerateResponse(
        success=True,
        message="Backup codes regenerated successfully. Save them in a safe place.",
        backup_codes=new_codes,
    )


# Email Verification Endpoints


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
            message="If an account with this email exists and is unverified, a verification email has been sent.",
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

    # Build verification URL
    frontend_url = get_config_value("frontend.url", settings.FRONTEND_URL, db)
    verification_url = f"{frontend_url}/verify-email/{new_token}"

    # Send verification email
    email_service = EmailService(db)
    display_name = user.display_name or user.email.split("@")[0]
    success, error = email_service.send_email_verification(
        to_email=user.email, user_name=display_name, verification_url=verification_url
    )

    if not success:
        logger.error(f"Failed to resend verification email to {user.email}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again later.",
        )

    logger.info(f"Verification email resent to: {user.email}")

    return EmailVerificationResponse(
        message="Verification email sent! Please check your inbox.", email=user.email
    )
