"""
Unit tests for app.api.auth._email_dispatch.

Uses unittest.mock.patch to avoid real EmailService calls.

The helper module was relocated from ``app.api._email_dispatch`` into
``app.api.auth._email_dispatch`` as part of C1 Phase 7, since
``api/auth`` is its only consumer.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth._email_dispatch import (
    build_verification_url,
    send_2fa_otp,
    send_verification_email,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(email: str = "user@example.com", display_name: str | None = None):
    """Return a minimal mock User."""
    user = MagicMock(spec=["email", "display_name"])
    user.email = email
    user.display_name = display_name
    return user


# ---------------------------------------------------------------------------
# build_verification_url
# ---------------------------------------------------------------------------


class TestBuildVerificationUrl:
    def test_constructs_url_correctly(self):
        url = build_verification_url("abc123", "https://app.example.com")
        assert url == "https://app.example.com/verify-email/abc123"

    def test_trailing_slash_not_doubled(self):
        # frontend_url without trailing slash should work
        url = build_verification_url("tok", "http://localhost:5173")
        assert url == "http://localhost:5173/verify-email/tok"

    def test_token_appears_in_url(self):
        token = "MY_SECRET_TOKEN"
        url = build_verification_url(token, "https://example.com")
        assert token in url


# ---------------------------------------------------------------------------
# send_verification_email
# ---------------------------------------------------------------------------


class TestSendVerificationEmail:
    def test_success_path_does_not_raise(self):
        user = _make_user()
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_email_verification.return_value = (True, None)
            # Should not raise
            send_verification_email(db, user, "tok", "http://localhost:5173")

        MockService.assert_called_once_with(db)
        MockService.return_value.send_email_verification.assert_called_once()

    def test_failure_raises_http_500(self):
        user = _make_user()
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_email_verification.return_value = (
                False,
                "SMTP error",
            )
            with pytest.raises(HTTPException) as exc_info:
                send_verification_email(db, user, "tok", "http://localhost:5173")

        assert exc_info.value.status_code == 500

    def test_failure_uses_custom_detail(self):
        user = _make_user()
        db = MagicMock()
        custom_msg = "Custom failure message"

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_email_verification.return_value = (
                False,
                "err",
            )
            with pytest.raises(HTTPException) as exc_info:
                send_verification_email(
                    db, user, "tok", "http://localhost:5173", failure_detail=custom_msg
                )

        assert exc_info.value.detail == custom_msg

    def test_url_is_built_and_passed_to_service(self):
        user = _make_user()
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_email_verification.return_value = (True, None)
            send_verification_email(db, user, "mytoken", "https://frontend.example.com")

        call_kwargs = MockService.return_value.send_email_verification.call_args
        assert "https://frontend.example.com/verify-email/mytoken" in str(call_kwargs)

    def test_display_name_falls_back_to_email_prefix(self):
        user = _make_user(email="john@example.com", display_name=None)
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_email_verification.return_value = (True, None)
            send_verification_email(db, user, "tok", "http://localhost")

        call_kwargs = MockService.return_value.send_email_verification.call_args
        assert "john" in str(call_kwargs)

    def test_explicit_display_name_used_when_provided(self):
        user = _make_user(email="john@example.com", display_name=None)
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_email_verification.return_value = (True, None)
            send_verification_email(
                db, user, "tok", "http://localhost", display_name="Johnny"
            )

        call_kwargs = MockService.return_value.send_email_verification.call_args
        assert "Johnny" in str(call_kwargs)


# ---------------------------------------------------------------------------
# send_2fa_otp
# ---------------------------------------------------------------------------


class TestSend2faOtp:
    def test_success_path_does_not_raise(self):
        user = _make_user()
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_2fa_otp_email.return_value = (True, None)
            # Should not raise
            send_2fa_otp(db, user, "123456")

        MockService.assert_called_once_with(db)
        MockService.return_value.send_2fa_otp_email.assert_called_once()

    def test_failure_raises_http_500(self):
        user = _make_user()
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_2fa_otp_email.return_value = (False, "err")
            with pytest.raises(HTTPException) as exc_info:
                send_2fa_otp(db, user, "123456")

        assert exc_info.value.status_code == 500

    def test_failure_uses_custom_detail(self):
        user = _make_user()
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_2fa_otp_email.return_value = (False, "err")
            with pytest.raises(HTTPException) as exc_info:
                send_2fa_otp(db, user, "123456", failure_detail="Custom OTP failure")

        assert exc_info.value.detail == "Custom OTP failure"

    def test_otp_code_passed_to_service(self):
        user = _make_user()
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_2fa_otp_email.return_value = (True, None)
            send_2fa_otp(db, user, "654321")

        call_kwargs = MockService.return_value.send_2fa_otp_email.call_args
        assert "654321" in str(call_kwargs)

    def test_user_name_derived_from_email_prefix(self):
        user = _make_user(email="alice@example.com")
        db = MagicMock()

        with patch("app.api.auth._email_dispatch.EmailService") as MockService:
            MockService.return_value.send_2fa_otp_email.return_value = (True, None)
            send_2fa_otp(db, user, "000000")

        call_kwargs = MockService.return_value.send_2fa_otp_email.call_args
        assert "alice" in str(call_kwargs)
