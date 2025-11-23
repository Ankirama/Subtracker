"""
Two-Factor Authentication utilities.
Supports TOTP (Time-based One-Time Password) and Email OTP.
"""
import pyotp
import qrcode
import io
import base64
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.two_factor import EmailOTP
from app.config import settings


class TOTPManager:
    """Manager for TOTP (Time-based One-Time Password) authentication."""

    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret key.

        Returns:
            Base32-encoded secret key
        """
        return pyotp.random_base32()

    @staticmethod
    def generate_provisioning_uri(secret: str, email: str) -> str:
        """
        Generate a provisioning URI for QR code.

        Args:
            secret: TOTP secret key
            email: User's email address

        Returns:
            Provisioning URI for authenticator apps
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=email,
            issuer_name=settings.APP_NAME
        )

    @staticmethod
    def generate_qr_code(secret: str, email: str) -> str:
        """
        Generate a QR code image for TOTP setup.

        Args:
            secret: TOTP secret key
            email: User's email address

        Returns:
            Base64-encoded PNG image of QR code
        """
        uri = TOTPManager.generate_provisioning_uri(secret, email)

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        # PyPNGImage doesn't support format argument, PIL Image does
        try:
            img.save(buffer, format='PNG')
        except TypeError:
            # Fallback for PyPNGImage (pypng backend)
            img.save(buffer)
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode()

        return f"data:image/png;base64,{img_base64}"

    @staticmethod
    def verify_code(secret: str, code: str, window: int = 1) -> bool:
        """
        Verify a TOTP code.

        Args:
            secret: TOTP secret key
            code: 6-digit code to verify
            window: Number of intervals to check before/after current time

        Returns:
            True if code is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=window)
        except Exception:
            return False


class EmailOTPManager:
    """Manager for Email-based One-Time Password authentication."""

    OTP_LENGTH = 6
    OTP_VALIDITY_MINUTES = 10

    @staticmethod
    def generate_code() -> str:
        """
        Generate a random 6-digit OTP code.

        Returns:
            6-digit numeric code as string
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(EmailOTPManager.OTP_LENGTH)])

    @staticmethod
    def create_otp(db: Session, user_id: str) -> str:
        """
        Create and store a new OTP code for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Generated OTP code
        """
        # Invalidate any existing unused codes
        existing_codes = db.query(EmailOTP).filter(
            EmailOTP.user_id == user_id,
            EmailOTP.is_used == 'N'
        ).all()

        for code in existing_codes:
            code.is_used = 'Y'

        # Generate new code
        code = EmailOTPManager.generate_code()
        expires_at = datetime.utcnow() + timedelta(minutes=EmailOTPManager.OTP_VALIDITY_MINUTES)

        # Store in database
        otp = EmailOTP(
            user_id=user_id,
            code=code,
            expires_at=expires_at,
            is_used='N'
        )

        db.add(otp)
        db.commit()

        return code

    @staticmethod
    def verify_code(db: Session, user_id: str, code: str) -> bool:
        """
        Verify an email OTP code.

        Args:
            db: Database session
            user_id: User ID
            code: OTP code to verify

        Returns:
            True if code is valid, False otherwise
        """
        otp = db.query(EmailOTP).filter(
            EmailOTP.user_id == user_id,
            EmailOTP.code == code,
            EmailOTP.is_used == 'N'
        ).first()

        if not otp:
            return False

        # Check if expired
        if otp.is_expired():
            return False

        # Mark as used
        otp.is_used = 'Y'
        db.commit()

        return True

    @staticmethod
    def cleanup_expired_codes(db: Session):
        """
        Clean up expired OTP codes from database.
        Should be run periodically.

        Args:
            db: Database session
        """
        db.query(EmailOTP).filter(
            EmailOTP.expires_at < datetime.utcnow()
        ).delete()
        db.commit()


class BackupCodesManager:
    """Manager for backup codes (used when 2FA device is unavailable)."""

    CODE_LENGTH = 8
    CODE_COUNT = 10

    @staticmethod
    def generate_codes() -> List[str]:
        """
        Generate a set of backup codes.

        Returns:
            List of backup codes (not hashed)
        """
        codes = []
        for _ in range(BackupCodesManager.CODE_COUNT):
            # Generate random alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                          for _ in range(BackupCodesManager.CODE_LENGTH))
            # Format as XXXX-XXXX
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)
        return codes

    @staticmethod
    def hash_code(code: str) -> str:
        """
        Hash a backup code for storage.

        Args:
            code: Plain backup code

        Returns:
            SHA-256 hash of the code
        """
        # Remove formatting dashes before hashing
        code = code.replace('-', '')
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def hash_codes(codes: List[str]) -> List[str]:
        """
        Hash multiple backup codes.

        Args:
            codes: List of plain backup codes

        Returns:
            List of hashed backup codes
        """
        return [BackupCodesManager.hash_code(code) for code in codes]

    @staticmethod
    def verify_code(code: str, hashed_codes: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Verify a backup code against stored hashes.

        Args:
            code: Plain backup code to verify
            hashed_codes: List of hashed backup codes from database

        Returns:
            Tuple of (is_valid, matched_hash)
        """
        code_hash = BackupCodesManager.hash_code(code)

        if code_hash in hashed_codes:
            return True, code_hash

        return False, None

    @staticmethod
    def remove_used_code(hashed_codes: List[str], used_code_hash: str) -> List[str]:
        """
        Remove a used backup code from the list.

        Args:
            hashed_codes: List of hashed backup codes
            used_code_hash: Hash of the code that was just used

        Returns:
            Updated list of backup codes with the used code removed
        """
        return [code for code in hashed_codes if code != used_code_hash]


class TwoFactorAuth:
    """Main interface for two-factor authentication operations."""

    @staticmethod
    def setup_totp(user: User) -> Tuple[str, str]:
        """
        Set up TOTP for a user.

        Args:
            user: User object

        Returns:
            Tuple of (secret, qr_code_data_uri)
        """
        secret = TOTPManager.generate_secret()
        qr_code = TOTPManager.generate_qr_code(secret, user.email)
        return secret, qr_code

    @staticmethod
    def enable_two_factor(
        db: Session,
        user: User,
        method: str,
        secret: Optional[str] = None
    ) -> List[str]:
        """
        Enable two-factor authentication for a user.

        Args:
            db: Database session
            user: User object
            method: '2FA method ('totp' or 'email')
            secret: TOTP secret (required for TOTP method)

        Returns:
            List of backup codes (plain, not hashed)
        """
        # Generate backup codes
        backup_codes = BackupCodesManager.generate_codes()
        hashed_codes = BackupCodesManager.hash_codes(backup_codes)

        # Update user
        user.two_factor_enabled = True
        user.two_factor_method = method
        user.two_factor_secret = secret
        user.backup_codes = hashed_codes

        db.commit()

        return backup_codes

    @staticmethod
    def disable_two_factor(db: Session, user: User):
        """
        Disable two-factor authentication for a user.

        Args:
            db: Database session
            user: User object
        """
        user.two_factor_enabled = False
        user.two_factor_method = None
        user.two_factor_secret = None
        user.backup_codes = []

        db.commit()

    @staticmethod
    def verify_two_factor(
        db: Session,
        user: User,
        code: str,
        is_backup_code: bool = False
    ) -> bool:
        """
        Verify a 2FA code for a user.

        Args:
            db: Database session
            user: User object
            code: Code to verify
            is_backup_code: Whether the code is a backup code

        Returns:
            True if code is valid, False otherwise
        """
        if not user.two_factor_enabled:
            return False

        # Check backup code first
        if is_backup_code or '-' in code:
            is_valid, used_hash = BackupCodesManager.verify_code(code, user.backup_codes)
            if is_valid and used_hash:
                # Remove used backup code
                user.backup_codes = BackupCodesManager.remove_used_code(
                    user.backup_codes,
                    used_hash
                )
                db.commit()
                return True
            return False

        # Verify based on method
        if user.two_factor_method == 'totp':
            return TOTPManager.verify_code(user.two_factor_secret, code)

        elif user.two_factor_method == 'email':
            return EmailOTPManager.verify_code(db, str(user.id), code)

        return False
