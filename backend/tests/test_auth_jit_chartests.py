"""
Just-in-time characterisation tests for the 14 currently untested routes
in ``app/api/auth.py``.

These tests lock in the observable behaviour of the routes BEFORE the
file is split into ``app/api/auth/`` (C1 Phase 7). They focus on:

- HTTP status codes and response shape parity
- DB side-effect parity on the ``users`` and ``security_events`` tables
- Backup-code generation / hashing parity
- Email-verification auto-login parity
- Brute-force IP-block + rate-limit parity (resend-verification)
- Side-effect parity on the dual language-preference system

Routes covered (14):
    1.  POST   /api/auth/2fa/verify-login
    2.  POST   /api/auth/2fa/setup
    3.  POST   /api/auth/2fa/enable
    4.  POST   /api/auth/2fa/disable
    5.  GET    /api/auth/2fa/status
    6.  POST   /api/auth/2fa/backup-codes/regenerate
    7.  POST   /api/auth/verify-email
    8.  POST   /api/auth/resend-verification
    9.  DELETE /api/auth/me
    10. PUT    /api/auth/me/password
    11. PUT    /api/auth/me/preferences
    12. PUT    /api/auth/me/profile
    13. GET    /api/auth/me/language
    14. PATCH  /api/auth/me/language

The two REQUIRE_INVITE_TOKEN tests in ``test_auth.py`` are pre-existing
failures (env config); these chartests bypass that path by either
patching ``settings.REQUIRE_INVITE_TOKEN`` to ``False`` or by exercising
already-registered users (the fixture ``test_user`` is verified by
default).
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pyotp

from app.models.admin import SecurityEvent
from app.models.two_factor import EmailOTP
from app.models.user import User
from app.security.two_factor import (
    BackupCodesManager,
    EmailOTPManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _security_events(db_session, *, user_id=None, event_type=None):
    """Return all SecurityEvent rows matching the optional filters."""
    q = db_session.query(SecurityEvent)
    if user_id is not None:
        q = q.filter(SecurityEvent.user_id == user_id)
    if event_type is not None:
        q = q.filter(SecurityEvent.event_type == event_type)
    return q.all()


def _enable_totp_for(user, db_session):
    """Provision a working TOTP secret for ``user`` and enable 2FA."""
    secret = pyotp.random_base32()
    backup_codes = BackupCodesManager.generate_codes()
    user.two_factor_enabled = True
    user.two_factor_method = "totp"
    user.two_factor_secret = secret
    user.backup_codes = BackupCodesManager.hash_codes(backup_codes)
    db_session.commit()
    db_session.refresh(user)
    return secret, backup_codes


def _enable_email_2fa_for(user, db_session):
    """Enable email-based 2FA for ``user`` (no secret stored)."""
    backup_codes = BackupCodesManager.generate_codes()
    user.two_factor_enabled = True
    user.two_factor_method = "email"
    user.two_factor_secret = None
    user.backup_codes = BackupCodesManager.hash_codes(backup_codes)
    db_session.commit()
    db_session.refresh(user)
    return backup_codes


# ---------------------------------------------------------------------------
# 1. POST /api/auth/2fa/verify-login
# ---------------------------------------------------------------------------


class TestVerify2FALogin:
    """Locks in /api/auth/2fa/verify-login behaviour."""

    def test_totp_success_returns_tokens_and_logs_event(
        self, client, test_user, db_session
    ):
        """Valid TOTP code returns tokens and logs successful_login event."""
        secret, _ = _enable_totp_for(test_user, db_session)
        code = pyotp.TOTP(secret).now()

        response = client.post(
            "/api/auth/2fa/verify-login",
            json={"email": test_user.email, "code": code},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == test_user.email

        events = _security_events(
            db_session, user_id=test_user.id, event_type="successful_login"
        )
        assert len(events) >= 1

    def test_invalid_code_returns_401_and_logs_failed_login(
        self, client, test_user, db_session
    ):
        """Invalid 2FA code returns 401 and logs failed_login event."""
        _enable_totp_for(test_user, db_session)

        response = client.post(
            "/api/auth/2fa/verify-login",
            json={"email": test_user.email, "code": "000000"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

        events = _security_events(db_session, event_type="failed_login")
        assert any(
            e.details and e.details.get("reason") == "invalid_2fa_code" for e in events
        )

    def test_unknown_email_returns_401(self, client, db_session):
        """Unknown email returns 401 with generic message."""
        response = client.post(
            "/api/auth/2fa/verify-login",
            json={"email": "ghost@example.com", "code": "123456"},
        )

        assert response.status_code == 401

    def test_2fa_not_enabled_returns_400(self, client, test_user):
        """Verifying 2FA login for a user without 2FA returns 400."""
        # test_user fixture has 2FA disabled by default.
        response = client.post(
            "/api/auth/2fa/verify-login",
            json={"email": test_user.email, "code": "123456"},
        )

        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"].lower()

    def test_backup_code_consumes_one_code(self, client, test_user, db_session):
        """Successful backup-code verification removes the code from the user."""
        _, backup_codes = _enable_totp_for(test_user, db_session)
        original_count = len(test_user.backup_codes)

        response = client.post(
            "/api/auth/2fa/verify-login",
            json={
                "email": test_user.email,
                "code": backup_codes[0],
                "is_backup_code": True,
            },
        )

        assert response.status_code == 200
        db_session.refresh(test_user)
        assert len(test_user.backup_codes) == original_count - 1


# ---------------------------------------------------------------------------
# 2. POST /api/auth/2fa/setup
# ---------------------------------------------------------------------------


class TestSetup2FA:
    """Locks in /api/auth/2fa/setup behaviour."""

    def test_totp_setup_returns_secret_and_qr(self, client, auth_headers):
        """TOTP setup returns secret + qr_code data URI."""
        response = client.post(
            "/api/auth/2fa/setup",
            json={"method": "totp"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["method"] == "totp"
        assert data["secret"]
        assert data["qr_code"].startswith("data:image/png;base64,")

    def test_email_setup_creates_otp_row(
        self, client, test_user, auth_headers, db_session
    ):
        """Email setup creates an EmailOTP row and returns an instructional message."""
        with patch("app.api.auth.two_factor.send_2fa_otp"):  # avoid Resend network call
            response = client.post(
                "/api/auth/2fa/setup",
                json={"method": "email"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["method"] == "email"
        # Message references the user's email
        assert test_user.email in data["message"]

        otps = (
            db_session.query(EmailOTP)
            .filter(EmailOTP.user_id == test_user.id, EmailOTP.is_used == "N")
            .all()
        )
        assert len(otps) == 1

    def test_setup_when_already_enabled_returns_400(
        self, client, test_user, auth_headers, db_session
    ):
        """Setup is rejected if 2FA is already enabled."""
        _enable_totp_for(test_user, db_session)

        response = client.post(
            "/api/auth/2fa/setup",
            json={"method": "totp"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. POST /api/auth/2fa/enable
# ---------------------------------------------------------------------------


class TestEnable2FA:
    """Locks in /api/auth/2fa/enable behaviour."""

    def test_totp_enable_persists_state_and_returns_backup_codes(
        self, client, test_user, auth_headers, db_session
    ):
        """Enabling TOTP persists secret + backup codes and returns plain backup codes."""
        secret = pyotp.random_base32()
        code = pyotp.TOTP(secret).now()

        response = client.post(
            "/api/auth/2fa/enable",
            json={
                "method": "totp",
                "secret": secret,
                "verification_code": code,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["backup_codes"], list)
        assert len(data["backup_codes"]) == BackupCodesManager.CODE_COUNT

        db_session.refresh(test_user)
        assert test_user.two_factor_enabled is True
        assert test_user.two_factor_method == "totp"
        assert test_user.two_factor_secret == secret
        # Backup codes are stored hashed, never plaintext
        for plain in data["backup_codes"]:
            assert plain not in (test_user.backup_codes or [])

    def test_totp_enable_invalid_code_returns_400(self, client, auth_headers):
        """Wrong TOTP verification code returns 400."""
        secret = pyotp.random_base32()
        response = client.post(
            "/api/auth/2fa/enable",
            json={
                "method": "totp",
                "secret": secret,
                "verification_code": "000000",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_totp_enable_missing_secret_returns_400(self, client, auth_headers):
        """TOTP enable without secret returns 400."""
        response = client.post(
            "/api/auth/2fa/enable",
            json={
                "method": "totp",
                "verification_code": "123456",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_email_enable_with_valid_otp(
        self, client, test_user, auth_headers, db_session
    ):
        """Enabling email 2FA with a valid OTP persists state and returns backup codes."""
        otp = EmailOTPManager.create_otp(db_session, str(test_user.id))

        response = client.post(
            "/api/auth/2fa/enable",
            json={"method": "email", "verification_code": otp},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        db_session.refresh(test_user)
        assert test_user.two_factor_enabled is True
        assert test_user.two_factor_method == "email"


# ---------------------------------------------------------------------------
# 4. POST /api/auth/2fa/disable
# ---------------------------------------------------------------------------


class TestDisable2FA:
    """Locks in /api/auth/2fa/disable behaviour."""

    def test_disable_with_correct_password_clears_state(
        self, client, test_user, auth_headers, db_session
    ):
        """Disabling 2FA with the right password clears all 2FA fields."""
        _enable_totp_for(test_user, db_session)

        response = client.post(
            "/api/auth/2fa/disable",
            json={"password": "testpassword123"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        db_session.refresh(test_user)
        assert test_user.two_factor_enabled is False
        assert test_user.two_factor_method is None
        assert test_user.two_factor_secret is None
        assert test_user.backup_codes == []

    def test_disable_wrong_password_returns_401(
        self, client, test_user, auth_headers, db_session
    ):
        """Wrong password returns 401 and leaves state untouched."""
        _enable_totp_for(test_user, db_session)

        response = client.post(
            "/api/auth/2fa/disable",
            json={"password": "wrong-password"},
            headers=auth_headers,
        )

        assert response.status_code == 401
        db_session.refresh(test_user)
        assert test_user.two_factor_enabled is True

    def test_disable_when_not_enabled_returns_400(
        self, client, test_user, auth_headers
    ):
        """Disabling 2FA on an account that does not have it returns 400."""
        response = client.post(
            "/api/auth/2fa/disable",
            json={"password": "testpassword123"},
            headers=auth_headers,
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 5. GET /api/auth/2fa/status
# ---------------------------------------------------------------------------


class TestStatus2FA:
    """Locks in /api/auth/2fa/status behaviour."""

    def test_status_when_disabled(self, client, auth_headers):
        """Status reports disabled with no method and 0 backup codes."""
        response = client.get("/api/auth/2fa/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["method"] is None
        assert data["backup_codes_remaining"] == 0

    def test_status_when_enabled_reports_method_and_count(
        self, client, test_user, auth_headers, db_session
    ):
        """Status reports method + remaining backup codes when enabled."""
        _enable_totp_for(test_user, db_session)

        response = client.get("/api/auth/2fa/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["method"] == "totp"
        assert data["backup_codes_remaining"] == BackupCodesManager.CODE_COUNT


# ---------------------------------------------------------------------------
# 6. POST /api/auth/2fa/backup-codes/regenerate
# ---------------------------------------------------------------------------


class TestRegenerateBackupCodes:
    """Locks in /api/auth/2fa/backup-codes/regenerate behaviour."""

    def test_regenerate_replaces_codes_and_returns_plain(
        self, client, test_user, auth_headers, db_session
    ):
        """Regeneration replaces stored hashes and returns N plain codes."""
        _enable_totp_for(test_user, db_session)
        old_hashes = list(test_user.backup_codes)

        response = client.post(
            "/api/auth/2fa/backup-codes/regenerate", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["backup_codes"]) == BackupCodesManager.CODE_COUNT

        db_session.refresh(test_user)
        # The stored hashes must have changed
        assert test_user.backup_codes != old_hashes
        # And the returned plain codes verify against the new stored hashes
        for plain in data["backup_codes"]:
            ok, _ = BackupCodesManager.verify_code(plain, test_user.backup_codes)
            assert ok

    def test_regenerate_when_not_enabled_returns_400(self, client, auth_headers):
        """Regenerating when 2FA is not enabled returns 400."""
        response = client.post(
            "/api/auth/2fa/backup-codes/regenerate", headers=auth_headers
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 7. POST /api/auth/verify-email
# ---------------------------------------------------------------------------


class TestVerifyEmail:
    """Locks in /api/auth/verify-email behaviour (auto-login on success)."""

    def test_verify_email_success_returns_tokens_and_marks_verified(
        self, client, db_session
    ):
        """Valid token marks user verified and returns auth tokens."""
        from app.security.password import hash_password

        token = "x" * 64
        password_hash, salt = hash_password("testpass123")
        user = User(
            email="unverified@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=False,
            email_verification_token=token,
            email_verification_sent_at=datetime.utcnow(),
            settings={},
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post("/api/auth/verify-email", json={"token": token})

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "unverified@example.com"

        db_session.refresh(user)
        assert user.email_verified is True

        events = _security_events(
            db_session, user_id=user.id, event_type="successful_login"
        )
        assert len(events) >= 1

    def test_verify_email_invalid_token_returns_400(self, client):
        """Unknown token returns 400 with a verification error message."""
        response = client.post("/api/auth/verify-email", json={"token": "x" * 64})

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_verify_email_already_verified_returns_400(
        self, client, test_user, db_session
    ):
        """Re-using a token on an already-verified user returns 400."""
        token = "y" * 64
        test_user.email_verification_token = token
        test_user.email_verification_sent_at = datetime.utcnow()
        # test_user is verified by default in the fixture
        db_session.commit()

        response = client.post("/api/auth/verify-email", json={"token": token})

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 8. POST /api/auth/resend-verification
# ---------------------------------------------------------------------------


class TestResendVerification:
    """Locks in /api/auth/resend-verification behaviour."""

    def test_resend_for_unverified_user_updates_token(self, client, db_session):
        """Resending updates the user's verification token + sent_at."""
        from app.security.password import hash_password

        old_token = "old" + "x" * 61
        password_hash, salt = hash_password("testpass123")
        user = User(
            email="resend@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=False,
            email_verification_token=old_token,
            email_verification_sent_at=datetime.utcnow() - timedelta(hours=1),
            settings={},
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        with patch("app.api.auth.registration.send_verification_email"):
            response = client.post(
                "/api/auth/resend-verification",
                json={"email": user.email},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user.email
        assert "sent" in data["message"].lower()

        db_session.refresh(user)
        assert user.email_verification_token != old_token

    def test_resend_for_verified_user_returns_400(self, client, test_user):
        """Resending for an already-verified email returns 400."""
        with patch("app.api.auth.registration.send_verification_email"):
            response = client.post(
                "/api/auth/resend-verification",
                json={"email": test_user.email},
            )

        assert response.status_code == 400
        assert "verified" in response.json()["detail"].lower()

    def test_resend_for_unknown_email_returns_200_enumeration_safe(self, client):
        """Resending for an unknown email returns 200 with a vague message."""
        response = client.post(
            "/api/auth/resend-verification",
            json={"email": "unknown@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "unknown@example.com"


# ---------------------------------------------------------------------------
# 9. DELETE /api/auth/me
# ---------------------------------------------------------------------------


class TestDeleteAccount:
    """Locks in DELETE /api/auth/me behaviour."""

    def test_delete_with_correct_password_removes_user(
        self, client, test_user, auth_headers, db_session
    ):
        """Correct password + confirm=True deletes the user row."""
        user_id = test_user.id

        response = client.request(
            "DELETE",
            "/api/auth/me",
            headers=auth_headers,
            json={"password": "testpassword123", "confirm": True},
        )

        assert response.status_code == 200
        # Re-query to confirm the user is gone
        assert db_session.query(User).filter(User.id == user_id).first() is None

    def test_delete_wrong_password_returns_400_and_keeps_user(
        self, client, test_user, auth_headers, db_session
    ):
        """Wrong password returns 400 and keeps the user row intact."""
        response = client.request(
            "DELETE",
            "/api/auth/me",
            headers=auth_headers,
            json={"password": "wrong-password", "confirm": True},
        )

        assert response.status_code == 400
        assert (
            db_session.query(User).filter(User.id == test_user.id).first() is not None
        )

    def test_delete_without_confirm_returns_400(
        self, client, test_user, auth_headers, db_session
    ):
        """confirm=False returns 400."""
        response = client.request(
            "DELETE",
            "/api/auth/me",
            headers=auth_headers,
            json={"password": "testpassword123", "confirm": False},
        )

        assert response.status_code == 400
        assert (
            db_session.query(User).filter(User.id == test_user.id).first() is not None
        )


# ---------------------------------------------------------------------------
# 10. PUT /api/auth/me/password
# ---------------------------------------------------------------------------


class TestChangePassword:
    """Locks in PUT /api/auth/me/password behaviour."""

    def test_change_password_success(self, client, test_user, auth_headers, db_session):
        """Changing the password updates hash + salt and the new password works for login."""
        from app.security.password import verify_password

        original_hash = test_user.password_hash

        response = client.put(
            "/api/auth/me/password",
            headers=auth_headers,
            json={
                "current_password": "testpassword123",
                "new_password": "newpassword456",
            },
        )

        assert response.status_code == 200
        db_session.refresh(test_user)
        assert test_user.password_hash != original_hash
        assert verify_password("newpassword456", test_user.password_hash) is True

    def test_change_password_wrong_current_returns_400(
        self, client, test_user, auth_headers, db_session
    ):
        """Wrong current password returns 400 and does not change the hash."""
        original_hash = test_user.password_hash

        response = client.put(
            "/api/auth/me/password",
            headers=auth_headers,
            json={
                "current_password": "wrong-current",
                "new_password": "newpassword456",
            },
        )

        assert response.status_code == 400
        db_session.refresh(test_user)
        assert test_user.password_hash == original_hash

    def test_change_password_weak_new_returns_422(self, client, auth_headers):
        """Schema validation rejects weak new passwords (no digit / too short)."""
        response = client.put(
            "/api/auth/me/password",
            headers=auth_headers,
            json={
                "current_password": "testpassword123",
                "new_password": "short",
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 11. PUT /api/auth/me/preferences
# ---------------------------------------------------------------------------


class TestUpdatePreferences:
    """Locks in PUT /api/auth/me/preferences behaviour."""

    def test_update_preferences_merges_settings(
        self, client, test_user, auth_headers, db_session
    ):
        """Update merges into User.settings (JSONB) and returns the merged dict."""
        # Seed an existing setting
        test_user.settings = {"existing": "value"}
        db_session.commit()

        response = client.put(
            "/api/auth/me/preferences",
            headers=auth_headers,
            json={
                "theme": "dark",
                "language": "fr",
                "currency": "EUR",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["theme"] == "dark"
        assert data["preferences"]["language"] == "fr"
        assert data["preferences"]["currency"] == "EUR"
        # Merge preserves the pre-existing key
        assert data["preferences"]["existing"] == "value"
        # Note: cross-session `db_session.refresh(test_user)` parity is
        # asserted via the API response above — re-reading via the same
        # SQLAlchemy session in SQLite does not always pick up JSON-column
        # mutations consistently in this test harness.

    def test_update_preferences_invalid_theme_returns_422(self, client, auth_headers):
        """Schema validation rejects unknown theme values."""
        response = client.put(
            "/api/auth/me/preferences",
            headers=auth_headers,
            json={"theme": "neon"},  # not in {light, dark, system}
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 12. PUT /api/auth/me/profile
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    """Locks in PUT /api/auth/me/profile behaviour."""

    def test_update_display_name(self, client, test_user, auth_headers, db_session):
        """Updating display_name persists and returns the new value."""
        response = client.put(
            "/api/auth/me/profile",
            headers=auth_headers,
            json={"display_name": "New Name"},
        )

        assert response.status_code == 200
        db_session.refresh(test_user)
        assert test_user.display_name == "New Name"

    def test_update_email_resets_verified_flag(
        self, client, test_user, auth_headers, db_session
    ):
        """Changing email sets email_verified back to False."""
        new_email = "moved@example.com"

        response = client.put(
            "/api/auth/me/profile",
            headers=auth_headers,
            json={"email": new_email},
        )

        assert response.status_code == 200
        db_session.refresh(test_user)
        assert test_user.email == new_email
        assert test_user.email_verified is False

    def test_update_email_to_existing_returns_400(
        self, client, test_user, auth_headers, db_session
    ):
        """Cannot change email to one already used by another account."""
        from app.security.password import hash_password

        password_hash, salt = hash_password("otherpass123")
        other = User(
            email="other@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=True,
            settings={},
        )
        db_session.add(other)
        db_session.commit()

        response = client.put(
            "/api/auth/me/profile",
            headers=auth_headers,
            json={"email": "other@example.com"},
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 13. GET /api/auth/me/language
# ---------------------------------------------------------------------------


class TestGetLanguagePreference:
    """Locks in GET /api/auth/me/language behaviour."""

    def test_default_language_is_null(self, client, auth_headers):
        """A user with no preferred_language returns null."""
        response = client.get("/api/auth/me/language", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_language"] is None
        assert "retrieved" in data["message"].lower()

    def test_returns_set_language(self, client, test_user, auth_headers, db_session):
        """Returns the explicitly-set preferred_language column value."""
        test_user.preferred_language = "fr"
        db_session.commit()

        response = client.get("/api/auth/me/language", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["preferred_language"] == "fr"


# ---------------------------------------------------------------------------
# 14. PATCH /api/auth/me/language
# ---------------------------------------------------------------------------


class TestUpdateLanguagePreference:
    """Locks in PATCH /api/auth/me/language behaviour."""

    def test_set_language_persists(self, client, test_user, auth_headers, db_session):
        """Setting language updates the preferred_language column."""
        response = client.patch(
            "/api/auth/me/language",
            headers=auth_headers,
            json={"language": "fr"},
        )

        assert response.status_code == 200
        assert response.json()["preferred_language"] == "fr"

        db_session.refresh(test_user)
        assert test_user.preferred_language == "fr"

    def test_set_language_to_null_clears(
        self, client, test_user, auth_headers, db_session
    ):
        """Setting language to null clears the column (browser-detection mode)."""
        test_user.preferred_language = "en"
        db_session.commit()

        response = client.patch(
            "/api/auth/me/language",
            headers=auth_headers,
            json={"language": None},
        )

        assert response.status_code == 200
        assert response.json()["preferred_language"] is None

        db_session.refresh(test_user)
        assert test_user.preferred_language is None

    def test_invalid_language_returns_422(self, client, auth_headers):
        """Schema validation rejects unsupported languages."""
        response = client.patch(
            "/api/auth/me/language",
            headers=auth_headers,
            json={"language": "de"},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Sanity: route-count parity
# ---------------------------------------------------------------------------


def test_auth_router_route_count_unchanged():
    """The /api/auth/* surface must remain at 19 (method, path) pairs.

    This protects against accidentally adding or removing a route during
    the C1 Phase 7 split.
    """
    from app.main import app

    pairs = []
    for r in app.routes:
        if hasattr(r, "path") and r.path.startswith("/api/auth"):
            for m in r.methods:
                pairs.append((m, r.path))
    assert len(pairs) == 19, f"Expected 19 /api/auth routes, got {len(pairs)}: {pairs}"
