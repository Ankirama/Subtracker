"""Account-management endpoints (profile, password, preferences, language, deletion).

Exposes:

  - ``PUT    /me/profile``       — update display_name and/or email.
  - ``PUT    /me/password``      — change password (requires current password).
  - ``PUT    /me/preferences``   — merge UI preferences into ``User.settings``.
  - ``GET    /me/language``      — read ``User.preferred_language``.
  - ``PATCH  /me/language``      — set ``User.preferred_language`` (or null).
  - ``DELETE /me``               — delete the account (requires password + confirm).

Note: the dual language-preference system (JSONB ``settings.language``
+ first-class ``preferred_language`` column) is intentionally preserved
in this module. Reconciling the two is tracked separately in audit §C.2.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    DeleteAccountRequest,
    LanguagePreferenceResponse,
    LanguagePreferenceUpdate,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    UserPreferencesUpdate,
    UserResponse,
)
from app.security.dependencies import get_current_user
from app.security.password import hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/me/language", response_model=LanguagePreferenceResponse)
async def get_language_preference(
    current_user: User = Depends(get_current_user),
):
    """
    Get user's language preference.

    Args:
        current_user: Current authenticated user

    Returns:
        User's preferred language or null for browser detection
    """
    return LanguagePreferenceResponse(
        preferred_language=current_user.preferred_language,
        message="Language preference retrieved successfully",
    )


@router.patch("/me/language", response_model=LanguagePreferenceResponse)
async def update_language_preference(
    language_data: LanguagePreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user's language preference.

    Args:
        language_data: Language preference update data (null for browser detection)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated language preference

    Raises:
        HTTPException: If validation fails
    """
    # Update language preference
    current_user.preferred_language = language_data.language
    db.commit()
    db.refresh(current_user)

    logger.info(
        "Language preference updated for user: "
        f"{current_user.email} to {language_data.language or 'browser detection'}"
    )
    return LanguagePreferenceResponse(
        preferred_language=current_user.preferred_language,
        message="Language preference updated successfully",
    )


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
