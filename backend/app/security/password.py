"""
Password hashing and verification using bcrypt.
"""
import bcrypt


def hash_password(password: str) -> tuple[str, str]:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Tuple of (password_hash, salt) as strings
    """
    # Generate salt
    salt = bcrypt.gensalt()

    # Hash password with salt
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)

    return password_hash.decode('utf-8'), salt.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        password_hash: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        password.encode('utf-8'),
        password_hash.encode('utf-8')
    )
