"""Login, refresh, logout, and current-user endpoints.

Exposes:

  - ``POST /login``    — credentials + brute-force tracking + 2FA challenge dispatch.
  - ``POST /refresh``  — rotate access token using a refresh token.
  - ``GET  /me``       — return the current authenticated user.
  - ``POST /logout``   — log a logout event (JWT is stateless).

The 2FA challenge that login may emit is *completed* by
``two_factor.verify_2fa_login`` — kept in a separate module because the
verification flow is its own concern.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.api.auth._email_dispatch import send_2fa_otp
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    TwoFactorRequiredResponse,
    UserLogin,
    UserResponse,
)
from app.security.dependencies import get_current_user
from app.security.events import (
    SecurityEventLogger,
    clear_failed_login_attempts,
    track_failed_login,
)
from app.security.jwt import create_access_token, create_refresh_token, verify_token
from app.security.password import verify_password
from app.security.two_factor import TwoFactorAuth

logger = logging.getLogger(__name__)

router = APIRouter()


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
            otp_code = TwoFactorAuth.create_email_otp(db, str(user.id))

            send_2fa_otp(db, user, otp_code)

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
