"""
Pydantic schemas for authentication endpoints.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    display_name: Optional[str] = Field(None, max_length=255, description="Optional display name for personalization")
    invite_token: Optional[str] = Field(None, description="Required invite token for registration (when enabled)")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isalpha() for c in v):
            raise ValueError('Password must contain at least one letter')
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response (without sensitive data)."""
    id: UUID
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # For SQLAlchemy models


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TwoFactorRequiredResponse(BaseModel):
    """Schema for 2FA required response during login."""
    requires_2fa: bool = True
    method: str  # 'totp' or 'email'
    message: str


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


class UserUpdate(BaseModel):
    """Schema for updating user settings."""
    settings: Optional[dict] = None


class ProfileUpdateRequest(BaseModel):
    """Schema for updating user profile."""
    display_name: Optional[str] = Field(None, max_length=255, description="Display name")
    email: Optional[EmailStr] = Field(None, description="New email address")


class PasswordChangeRequest(BaseModel):
    """Schema for changing password."""
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isalpha() for c in v):
            raise ValueError('Password must contain at least one letter')
        return v


class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences."""
    theme: Optional[str] = Field(None, pattern="^(light|dark|system)$", description="UI theme preference")
    language: Optional[str] = Field(None, pattern="^[a-z]{2}(-[A-Z]{2})?$", description="Language code (e.g., 'en', 'fr', 'en-US')")
    currency: Optional[str] = Field(None, pattern="^[A-Z]{3}$", description="Currency code (e.g., 'USD', 'EUR')")
    date_format: Optional[str] = Field(None, description="Preferred date format")
    timezone: Optional[str] = Field(None, description="User timezone")


class DeleteAccountRequest(BaseModel):
    """Schema for account deletion."""
    password: str = Field(..., description="Current password for verification")
    confirm: bool = Field(..., description="Confirmation flag")


# Two-Factor Authentication Schemas

class TwoFactorSetupRequest(BaseModel):
    """Schema for initiating 2FA setup."""
    method: str = Field(..., pattern="^(totp|email)$", description="2FA method: 'totp' or 'email'")


class TwoFactorSetupResponse(BaseModel):
    """Schema for 2FA setup response."""
    method: str
    secret: Optional[str] = None  # TOTP secret (only for TOTP method)
    qr_code: Optional[str] = None  # Base64 QR code data URI (only for TOTP method)
    message: str


class TwoFactorEnableRequest(BaseModel):
    """Schema for enabling 2FA (requires verification)."""
    method: str = Field(..., pattern="^(totp|email)$")
    secret: Optional[str] = None  # Required for TOTP
    verification_code: str = Field(..., min_length=6, max_length=8, description="6-digit code or 8-char backup code")


class TwoFactorEnableResponse(BaseModel):
    """Schema for 2FA enable response with backup codes."""
    success: bool
    message: str
    backup_codes: list[str]  # List of backup codes (only shown once)


class TwoFactorDisableRequest(BaseModel):
    """Schema for disabling 2FA."""
    password: str = Field(..., description="User's password for confirmation")


class TwoFactorVerifyRequest(BaseModel):
    """Schema for verifying 2FA code during login."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=9, description="6-digit OTP or 8-char backup code (XXXX-XXXX)")
    is_backup_code: bool = False


class TwoFactorStatusResponse(BaseModel):
    """Schema for current 2FA status."""
    enabled: bool
    method: Optional[str] = None  # 'totp' or 'email'
    backup_codes_remaining: int = 0


class BackupCodesRegenerateResponse(BaseModel):
    """Schema for regenerated backup codes."""
    success: bool
    message: str
    backup_codes: list[str]


# Email Verification Schemas

class EmailVerificationResponse(BaseModel):
    """Schema for registration response requiring email verification."""
    message: str
    email: str


class EmailVerificationRequest(BaseModel):
    """Schema for verifying email with token."""
    token: str = Field(..., min_length=32, max_length=255)


class ResendVerificationRequest(BaseModel):
    """Schema for resending verification email."""
    email: EmailStr
