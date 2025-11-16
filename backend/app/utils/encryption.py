"""
Encryption utility for securing sensitive data like API keys
Uses Fernet symmetric encryption from the cryptography library
"""
from cryptography.fernet import Fernet
from app.config import settings
import base64


class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""

    def __init__(self):
        """Initialize the encryption service with the key from settings"""
        # Ensure the key is properly formatted for Fernet (base64-encoded)
        try:
            # If the key is already base64-encoded, use it directly
            self.cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        except Exception:
            # If not, try to encode it as base64
            key = base64.urlsafe_b64encode(settings.ENCRYPTION_KEY.encode().ljust(32)[:32])
            self.cipher = Fernet(key)

    def encrypt(self, value: str) -> str:
        """
        Encrypt a string value

        Args:
            value: The plain text string to encrypt

        Returns:
            The encrypted value as a base64-encoded string
        """
        if not value:
            return value

        encrypted_bytes = self.cipher.encrypt(value.encode())
        return encrypted_bytes.decode()

    def decrypt(self, encrypted_value: str) -> str:
        """
        Decrypt an encrypted string value

        Args:
            encrypted_value: The encrypted value as a base64-encoded string

        Returns:
            The decrypted plain text string

        Raises:
            cryptography.fernet.InvalidToken: If the token is invalid or corrupted
        """
        if not encrypted_value:
            return encrypted_value

        decrypted_bytes = self.cipher.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()


# Singleton instance
encryption_service = EncryptionService()
