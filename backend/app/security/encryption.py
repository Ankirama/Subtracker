"""
Credential encryption using Fernet (symmetric encryption).
Used for encrypting mailbox credentials (OAuth tokens, etc.).
"""
from cryptography.fernet import Fernet
import json
from app.config import settings


# Initialize cipher with key from settings
_cipher = Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_credentials(credentials: dict) -> str:
    """
    Encrypt credentials dictionary to string.

    Args:
        credentials: Dictionary containing sensitive credentials

    Returns:
        Encrypted string
    """
    json_str = json.dumps(credentials)
    encrypted = _cipher.encrypt(json_str.encode())
    return encrypted.decode()


def decrypt_credentials(encrypted_credentials: str) -> dict:
    """
    Decrypt credentials string to dictionary.

    Args:
        encrypted_credentials: Encrypted credentials string

    Returns:
        Decrypted credentials dictionary
    """
    decrypted = _cipher.decrypt(encrypted_credentials.encode())
    return json.loads(decrypted.decode())


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        Base64-encoded encryption key

    Note:
        This is a utility function. In production, generate once and store in environment.
    """
    return Fernet.generate_key().decode()
