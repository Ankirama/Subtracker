"""
Tests for Authentication API endpoints and security functions.

Tests cover:
- User registration (success, duplicate email, validation)
- User login (success, wrong credentials, inactive user)
- Token refresh (success, invalid token, wrong type)
- Current user endpoints (/me, logout)
- Encryption/decryption of credentials
- Token validation and dependencies
- Admin user checks
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from jose import jwt

from app.security.encryption import encrypt_credentials, decrypt_credentials, generate_encryption_key
from app.security.jwt import create_access_token, create_refresh_token, verify_token, get_user_id_from_token
from app.security.dependencies import get_current_user, get_current_admin_user
from app.config import settings


class TestUserRegistration:
    """Test POST /api/auth/register - user registration."""

    def test_register_success(self, client):
        """Successfully register a new user (returns verification message, not tokens)."""
        from unittest.mock import patch

        # Mock email service to prevent actual email sending
        with patch('app.services.email_service.EmailService.send_email_verification') as mock_email:
            mock_email.return_value = (True, None)

            user_data = {
                "email": "newuser@example.com",
                "password": "securepassword123"
            }

            response = client.post("/api/auth/register", json=user_data)

            assert response.status_code == 201
            data = response.json()

            # Email verification required - no tokens returned
            assert "access_token" not in data
            assert "refresh_token" not in data

            # Should have verification response
            assert "message" in data
            assert "email" in data
            assert data["email"] == "newuser@example.com"
            assert "verify" in data["message"].lower()

    def test_register_duplicate_email(self, client, test_user):
        """Cannot register with existing email."""
        user_data = {
            "email": test_user.email,  # Existing email
            "password": "somepassword123"
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client):
        """Cannot register with invalid email format."""
        user_data = {
            "email": "notanemail",  # Invalid email
            "password": "securepassword123"
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_register_weak_password(self, client):
        """Cannot register with weak password."""
        user_data = {
            "email": "newuser@example.com",
            "password": "123"  # Too short
        }

        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """Test POST /api/auth/login - user login."""

    def test_login_success(self, client, test_user):
        """Successfully login with correct credentials."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"  # From conftest.py fixture
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert data["user"]["email"] == test_user.email

    def test_login_wrong_password(self, client, test_user):
        """Cannot login with wrong password."""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_email(self, client):
        """Cannot login with non-existent email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_inactive_user(self, client, test_user, db_session):
        """Cannot login with inactive user account."""
        # Deactivate user
        test_user.is_active = False
        db_session.commit()

        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }

        response = client.post("/api/auth/login", json=login_data)

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()


class TestTokenRefresh:
    """Test POST /api/auth/refresh - refresh access token."""

    def test_refresh_token_success(self, client, test_user):
        """Successfully refresh access token with valid refresh token."""
        # Login to get refresh token
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword123"}
        )
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token to get new access token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_refresh_with_access_token_fails(self, client, test_user):
        """Cannot refresh using access token (must use refresh token)."""
        # Login to get access token
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword123"}
        )
        access_token = login_response.json()["access_token"]

        # Try to use access token for refresh (should fail)
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": access_token}
        )

        assert response.status_code == 401
        assert "invalid token type" in response.json()["detail"].lower()

    def test_refresh_with_invalid_token(self, client):
        """Cannot refresh with invalid token."""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid.token.here"}
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_refresh_with_expired_token(self, client, test_user):
        """Cannot refresh with expired token."""
        # Create expired refresh token
        expired_token = jwt.encode(
            {
                "user_id": str(test_user.id),
                "type": "refresh",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1)  # Expired
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": expired_token}
        )

        assert response.status_code == 401

    def test_refresh_token_inactive_user(self, client, test_user, db_session):
        """Cannot refresh token for inactive user."""
        # Get refresh token while active
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword123"}
        )
        refresh_token = login_response.json()["refresh_token"]

        # Deactivate user
        test_user.is_active = False
        db_session.commit()

        # Try to refresh (should fail)
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()


class TestCurrentUserEndpoints:
    """Test /me and /logout endpoints."""

    def test_get_current_user_success(self, client, auth_headers):
        """Get current user info with valid token."""
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert data["email"] == "test@example.com"

    def test_get_current_user_no_token(self, client):
        """Cannot get current user without token."""
        response = client.get("/api/auth/me")

        assert response.status_code == 403

    def test_get_current_user_invalid_token(self, client):
        """Cannot get current user with invalid token."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401

    def test_logout_success(self, client, auth_headers):
        """Successfully logout with valid token."""
        response = client.post("/api/auth/logout", headers=auth_headers)

        assert response.status_code == 200
        assert "message" in response.json()

    def test_logout_no_token(self, client):
        """Cannot logout without token."""
        response = client.post("/api/auth/logout")

        assert response.status_code == 403


class TestEncryption:
    """Test credential encryption and decryption."""

    def test_encrypt_decrypt_credentials(self):
        """Encrypt and decrypt credentials successfully."""
        original_credentials = {
            "username": "testuser",
            "password": "testpass123",
            "api_key": "secret-key-123",
            "tokens": {
                "access": "access-token",
                "refresh": "refresh-token"
            }
        }

        # Encrypt
        encrypted = encrypt_credentials(original_credentials)
        assert isinstance(encrypted, str)
        assert encrypted != str(original_credentials)

        # Decrypt
        decrypted = decrypt_credentials(encrypted)
        assert decrypted == original_credentials

    def test_encrypt_empty_dict(self):
        """Can encrypt and decrypt empty dictionary."""
        empty_creds = {}

        encrypted = encrypt_credentials(empty_creds)
        decrypted = decrypt_credentials(encrypted)

        assert decrypted == empty_creds

    def test_encrypt_complex_data(self):
        """Can encrypt and decrypt complex nested data."""
        complex_creds = {
            "oauth": {
                "provider": "google",
                "tokens": {
                    "access_token": "xyz123",
                    "refresh_token": "abc456",
                    "expires_at": 1234567890
                },
                "scopes": ["email", "profile"]
            },
            "metadata": {
                "created_at": "2024-01-01",
                "updated_at": "2024-01-15"
            }
        }

        encrypted = encrypt_credentials(complex_creds)
        decrypted = decrypt_credentials(encrypted)

        assert decrypted == complex_creds

    def test_decrypt_invalid_data_fails(self):
        """Decrypting invalid data raises error."""
        with pytest.raises(Exception):
            decrypt_credentials("not-valid-encrypted-data")

    def test_generate_encryption_key(self):
        """Can generate new encryption key."""
        key = generate_encryption_key()

        assert isinstance(key, str)
        assert len(key) > 0
        # Fernet keys are base64 encoded and have specific length
        assert len(key) == 44


class TestJWTTokens:
    """Test JWT token creation and verification."""

    def test_create_and_verify_access_token(self, test_user):
        """Create and verify access token."""
        user_id = str(test_user.id)

        # Create token
        token = create_access_token(user_id)
        assert isinstance(token, str)

        # Verify token
        payload = verify_token(token)
        assert payload["user_id"] == user_id
        assert payload["type"] == "access"

    def test_create_and_verify_refresh_token(self, test_user):
        """Create and verify refresh token."""
        user_id = str(test_user.id)

        # Create token
        token = create_refresh_token(user_id)
        assert isinstance(token, str)

        # Verify token
        payload = verify_token(token)
        assert payload["user_id"] == user_id
        assert payload["type"] == "refresh"

    def test_get_user_id_from_token(self, test_user):
        """Extract user ID from token."""
        user_id = str(test_user.id)
        token = create_access_token(user_id)

        extracted_id = get_user_id_from_token(token)

        assert extracted_id == user_id

    def test_verify_invalid_token_fails(self):
        """Verifying invalid token raises error."""
        from jose import JWTError

        with pytest.raises(JWTError):
            verify_token("invalid.token.here")

    def test_verify_expired_token_fails(self, test_user):
        """Verifying expired token raises error."""
        from jose import JWTError

        # Create expired token
        expired_token = jwt.encode(
            {
                "user_id": str(test_user.id),
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1)
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        with pytest.raises(JWTError):
            verify_token(expired_token)


class TestAuthenticationDependencies:
    """Test authentication dependency functions."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, db_session, test_user):
        """get_current_user returns user with valid token."""
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token(str(test_user.id))
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        user = await get_current_user(credentials, db_session)

        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, db_session):
        """get_current_user raises HTTPException with invalid token."""
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, db_session)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self, db_session):
        """get_current_user raises HTTPException when user doesn't exist."""
        from fastapi.security import HTTPAuthorizationCredentials
        import uuid

        # Create token for non-existent user
        fake_user_id = str(uuid.uuid4())
        token = create_access_token(fake_user_id)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, db_session)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_inactive_user(self, db_session, test_user):
        """get_current_user raises HTTPException for inactive user."""
        from fastapi.security import HTTPAuthorizationCredentials

        # Deactivate user
        test_user.is_active = False
        db_session.commit()

        token = create_access_token(str(test_user.id))
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, db_session)

        assert exc_info.value.status_code == 403
        assert "inactive" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_admin_user_success(self, db_session, test_user):
        """get_current_admin_user succeeds for admin user."""
        # Make user admin
        test_user.is_admin = True
        db_session.commit()

        admin_user = await get_current_admin_user(test_user)

        assert admin_user.id == test_user.id
        assert admin_user.is_admin is True

    @pytest.mark.asyncio
    async def test_get_current_admin_user_non_admin_fails(self, test_user):
        """get_current_admin_user raises HTTPException for non-admin user."""
        # Ensure user is not admin
        test_user.is_admin = False

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(test_user)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_admin_user_inactive_fails(self, test_user):
        """get_current_admin_user raises HTTPException for inactive admin."""
        # Make user admin but inactive
        test_user.is_admin = True
        test_user.is_active = False

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(test_user)

        assert exc_info.value.status_code == 403
        assert "inactive" in exc_info.value.detail.lower()
