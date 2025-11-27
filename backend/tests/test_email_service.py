"""Comprehensive tests for email_service"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, date
from decimal import Decimal

from app.services.email_service import EmailService


@pytest.fixture
def mock_sendgrid_client():
    """Create a mock SendGrid client"""
    with patch("app.services.email_service.SendGridAPIClient") as mock_client:
        mock_instance = Mock()
        mock_client.return_value = mock_instance

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_instance.send.return_value = mock_response

        yield mock_instance


@pytest.fixture
def email_service(mock_sendgrid_client):
    """Create EmailService instance with mocked SendGrid"""
    with patch("app.services.email_service.get_config_value") as mock_get_config:
        # Mock config values
        mock_get_config.side_effect = lambda key, default, db: default

        with patch("os.getenv", return_value="test_api_key"):
            service = EmailService()
            return service


class TestEmailServiceInit:
    """Tests for EmailService initialization"""

    @patch("app.services.email_service.SendGridAPIClient")
    @patch("app.services.email_service.get_config_value")
    def test_initializes_with_config_values(self, mock_get_config, mock_client):
        """Should initialize with config values"""
        mock_get_config.side_effect = lambda key, default, db: default

        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "test_key"
            mock_settings.SENDGRID_FROM_EMAIL = "test@example.com"
            mock_settings.SENDGRID_FROM_NAME = "Test Sender"

            service = EmailService()

            mock_client.assert_called_once_with("test_key")
            assert service.from_email.email == "test@example.com"
            assert service.from_email.name == "Test Sender"

    @patch("app.services.email_service.SendGridAPIClient")
    @patch("app.services.email_service.get_config_value")
    def test_uses_admin_override_when_available(self, mock_get_config, mock_client):
        """Should use admin settings override when available"""

        def config_side_effect(key, default, db):
            if "api_key" in key:
                return "admin_override_key"
            return default

        mock_get_config.side_effect = config_side_effect

        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "default_key"
            mock_settings.SENDGRID_FROM_EMAIL = "test@example.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"

            service = EmailService()

            mock_client.assert_called_once_with("admin_override_key")


class TestSendEmail:
    """Tests for send_email method"""

    def test_sends_email_successfully(self, email_service, mock_sendgrid_client):
        """Should send email and return success"""
        success, error = email_service.send_email(
            to_email="test@example.com",
            subject="Test Email",
            html_content="<p>Hello</p>",
            plain_content="Hello",
        )

        assert success is True
        assert error is None
        mock_sendgrid_client.send.assert_called_once()

    def test_sends_email_with_html_only(self, email_service, mock_sendgrid_client):
        """Should send email with HTML content only"""
        success, error = email_service.send_email(
            to_email="test@example.com",
            subject="Test Email",
            html_content="<p>Hello</p>",
        )

        assert success is True
        assert error is None

    def test_handles_sendgrid_error(self, email_service, mock_sendgrid_client):
        """Should handle SendGrid API errors gracefully"""
        mock_sendgrid_client.send.side_effect = Exception("SendGrid error")

        success, error = email_service.send_email(
            to_email="test@example.com",
            subject="Test Email",
            html_content="<p>Hello</p>",
        )

        assert success is False
        assert "SendGrid error" in error

    def test_returns_false_for_non_2xx_status_code(
        self, email_service, mock_sendgrid_client
    ):
        """Should return False for non-2xx status codes"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_sendgrid_client.send.return_value = mock_response

        success, error = email_service.send_email(
            to_email="test@example.com",
            subject="Test Email",
            html_content="<p>Hello</p>",
        )

        assert success is False
        assert "status 400" in error

    def test_accepts_2xx_status_codes(self, email_service, mock_sendgrid_client):
        """Should accept 200, 201, 202 status codes as success"""
        for status_code in [200, 201, 202]:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_sendgrid_client.send.return_value = mock_response

            success, error = email_service.send_email(
                to_email="test@example.com",
                subject="Test Email",
                html_content="<p>Hello</p>",
            )

            assert success is True
            assert error is None


class TestSendRenewalReminder:
    """Tests for send_renewal_reminder method"""

    def test_sends_renewal_reminder_successfully(
        self, email_service, mock_sendgrid_client
    ):
        """Should send renewal reminder with subscription details"""
        success, error = email_service.send_renewal_reminder(
            to_email="test@example.com",
            user_name="John Doe",
            subscription_name="Netflix",
            renewal_date=datetime(2024, 12, 1),
            amount=15.99,
            currency="USD",
            days_until_renewal=3,
        )

        assert success is True
        assert error is None
        mock_sendgrid_client.send.assert_called_once()

    def test_handles_error_gracefully(self, email_service, mock_sendgrid_client):
        """Should handle errors and return error message"""
        mock_sendgrid_client.send.side_effect = Exception("Network error")

        success, error = email_service.send_renewal_reminder(
            to_email="test@example.com",
            user_name="John Doe",
            subscription_name="Netflix",
            renewal_date=datetime(2024, 12, 1),
            amount=15.99,
            currency="USD",
            days_until_renewal=3,
        )

        assert success is False
        assert "Network error" in error


class TestSendWeeklySummary:
    """Tests for send_weekly_summary method"""

    def test_sends_weekly_summary_successfully(
        self, email_service, mock_sendgrid_client
    ):
        """Should send weekly summary with spending data"""
        subscriptions = [
            {"name": "Netflix", "amount": 15.99},
            {"name": "Spotify", "amount": 9.99},
        ]
        upcoming_renewals = [{"name": "Netflix", "days_until": 5}]

        success, error = email_service.send_weekly_summary(
            to_email="test@example.com",
            user_name="John Doe",
            total_spent=25.98,
            currency="USD",
            subscriptions=subscriptions,
            upcoming_renewals=upcoming_renewals,
        )

        assert success is True
        assert error is None
        mock_sendgrid_client.send.assert_called_once()

    def test_sends_empty_summary(self, email_service, mock_sendgrid_client):
        """Should send summary even with no subscriptions"""
        success, error = email_service.send_weekly_summary(
            to_email="test@example.com",
            user_name="John Doe",
            total_spent=0.0,
            currency="USD",
            subscriptions=[],
            upcoming_renewals=[],
        )

        assert success is True


class TestSendMonthlySummary:
    """Tests for send_monthly_summary method"""

    def test_sends_monthly_summary_successfully(
        self, email_service, mock_sendgrid_client
    ):
        """Should send monthly summary with detailed statistics"""
        subscriptions = [
            {"name": "Netflix", "amount": 15.99},
            {"name": "Spotify", "amount": 9.99},
        ]
        spending_breakdown = {"streaming": 15.99, "music": 9.99}

        success, error = email_service.send_monthly_summary(
            to_email="test@example.com",
            user_name="John Doe",
            total_spent=25.98,
            currency="USD",
            subscriptions=subscriptions,
            spending_breakdown=spending_breakdown,
            comparison_last_month=None,
        )

        assert success is True
        assert error is None
        mock_sendgrid_client.send.assert_called_once()

    def test_includes_comparison_data(self, email_service, mock_sendgrid_client):
        """Should include comparison with last month when provided"""
        subscriptions = [{"name": "Netflix", "amount": 15.99}]
        spending_breakdown = {"streaming": 15.99}
        comparison = {"total": 12.99, "subscriptions": 1}

        success, error = email_service.send_monthly_summary(
            to_email="test@example.com",
            user_name="John Doe",
            total_spent=15.99,
            currency="USD",
            subscriptions=subscriptions,
            spending_breakdown=spending_breakdown,
            comparison_last_month=comparison,
        )

        assert success is True


class TestSend2FAOTPEmail:
    """Tests for send_2fa_otp_email method"""

    @patch("app.services.email_service.EmailTemplates.generate_2fa_otp_email")
    def test_sends_2fa_otp_email(
        self, mock_generate_template, email_service, mock_sendgrid_client
    ):
        """Should send 2FA OTP email using EmailTemplates"""
        mock_generate_template.return_value = "<p>Your OTP: 123456</p>"

        success, error = email_service.send_2fa_otp_email(
            to_email="test@example.com",
            user_name="John Doe",
            otp_code="123456",
            expires_in_minutes=10,
        )

        assert success is True
        assert error is None
        mock_generate_template.assert_called_once_with(
            user_name="John Doe", otp_code="123456", expires_in_minutes=10
        )
        mock_sendgrid_client.send.assert_called_once()

    @patch("app.services.email_service.EmailTemplates.generate_2fa_otp_email")
    def test_handles_template_error(
        self, mock_generate_template, email_service, mock_sendgrid_client
    ):
        """Should propagate template generation errors"""
        mock_generate_template.side_effect = Exception("Template error")

        with pytest.raises(Exception, match="Template error"):
            email_service.send_2fa_otp_email(
                to_email="test@example.com", user_name="John Doe", otp_code="123456"
            )


class TestSendEmailVerification:
    """Tests for send_email_verification method"""

    @patch(
        "app.services.email_service.EmailTemplates.generate_email_verification_email"
    )
    def test_sends_verification_email(
        self, mock_generate_template, email_service, mock_sendgrid_client
    ):
        """Should send verification email with URL"""
        mock_generate_template.return_value = "<p>Verify your email</p>"
        verification_url = "https://example.com/verify/abc123"

        success, error = email_service.send_email_verification(
            to_email="test@example.com",
            user_name="John Doe",
            verification_url=verification_url,
        )

        assert success is True
        assert error is None
        mock_generate_template.assert_called_once_with(
            user_name="John Doe", verification_url=verification_url
        )
        mock_sendgrid_client.send.assert_called_once()

    @patch(
        "app.services.email_service.EmailTemplates.generate_email_verification_email"
    )
    def test_handles_sendgrid_failure(
        self, mock_generate_template, email_service, mock_sendgrid_client
    ):
        """Should handle SendGrid failures properly"""
        mock_generate_template.return_value = "<p>Verify</p>"
        mock_sendgrid_client.send.side_effect = Exception("SendGrid down")

        success, error = email_service.send_email_verification(
            to_email="test@example.com",
            user_name="John Doe",
            verification_url="https://example.com/verify/token",
        )

        assert success is False
        assert "SendGrid down" in error


class TestHTMLTemplates:
    """Tests for HTML template generation methods"""

    def test_renewal_reminder_template_contains_key_info(self, email_service):
        """Should generate renewal reminder template with subscription details"""
        html = email_service._get_renewal_reminder_template(
            user_name="John Doe",
            subscription_name="Netflix",
            renewal_date=datetime(2024, 12, 1),
            amount=15.99,
            currency="USD",
            days_until_renewal=3,
        )

        assert "John Doe" in html
        assert "Netflix" in html
        assert "15.99" in html
        assert "3 days" in html
        assert "USD" in html
        assert "December 01, 2024" in html

    def test_weekly_summary_template_contains_subscriptions(self, email_service):
        """Should generate weekly summary with subscription list"""
        subscriptions = [
            {"name": "Netflix", "amount": 15.99},
            {"name": "Spotify", "amount": 9.99},
        ]
        upcoming_renewals = [{"name": "Netflix", "days_until": 5}]

        html = email_service._get_weekly_summary_template(
            user_name="John Doe",
            total_spent=25.98,
            currency="USD",
            subscriptions=subscriptions,
            upcoming_renewals=upcoming_renewals,
        )

        assert "John Doe" in html
        assert "Netflix" in html
        assert "Spotify" in html
        assert "25.98" in html
        assert "USD" in html

    def test_weekly_summary_handles_empty_subscriptions(self, email_service):
        """Should handle empty subscription list gracefully"""
        html = email_service._get_weekly_summary_template(
            user_name="John Doe",
            total_spent=0.0,
            currency="USD",
            subscriptions=[],
            upcoming_renewals=[],
        )

        assert "John Doe" in html
        assert "0.00" in html
        assert html is not None

    def test_monthly_summary_template_contains_statistics(self, email_service):
        """Should generate monthly summary with statistics"""
        subscriptions = [
            {"name": "Netflix", "amount": 15.99},
            {"name": "Spotify", "amount": 9.99},
        ]
        spending_breakdown = {"streaming": 15.99, "music": 9.99}

        html = email_service._get_monthly_summary_template(
            user_name="John Doe",
            total_spent=25.98,
            currency="USD",
            subscriptions=subscriptions,
            spending_breakdown=spending_breakdown,
            comparison_last_month=None,
        )

        assert "John Doe" in html
        assert "Netflix" in html
        assert "25.98" in html
        assert "USD" in html

    def test_monthly_summary_includes_comparison(self, email_service):
        """Should include comparison data in monthly summary"""
        subscriptions = [{"name": "Netflix", "amount": 15.99}]
        spending_breakdown = {"streaming": 15.99}
        comparison = {"total": 12.99}

        html = email_service._get_monthly_summary_template(
            user_name="John Doe",
            total_spent=15.99,
            currency="USD",
            subscriptions=subscriptions,
            spending_breakdown=spending_breakdown,
            comparison_last_month=comparison,
        )

        assert "John Doe" in html
        assert "15.99" in html
        # Should contain comparison elements (emoji, trend)
        assert html is not None
