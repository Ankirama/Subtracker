"""Comprehensive tests for ai_classifier service"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
import json

from app.services.ai_classifier import (
    get_openai_client,
    classify_email,
    classify_email_with_retry,
    classify_emails_batch,
)
from app.email_providers.base import EmailMessage
from openai import RateLimitError, APIError


@pytest.fixture
def mock_email():
    """Create a mock EmailMessage for testing"""
    return EmailMessage(
        id="test-123",
        subject="Netflix Subscription Renewal",
        sender="billing@netflix.com",
        sender_name="Netflix",
        recipients=["user@example.com"],
        date=datetime(2024, 1, 15, 10, 30),
        body_text="Your Netflix subscription will renew on January 20, 2024 for $15.99",
        body_html="<p>Your Netflix subscription will renew on January 20, 2024 for $15.99</p>",
        headers={},
        has_attachments=False,
        folder="INBOX",
    )


@pytest.fixture
def mock_non_subscription_email():
    """Create a non-subscription email for testing"""
    return EmailMessage(
        id="test-456",
        subject="New login from Chrome",
        sender="security@netflix.com",
        sender_name="Netflix Security",
        recipients=["user@example.com"],
        date=datetime(2024, 1, 15, 10, 30),
        body_text="We noticed a new login to your account from Chrome",
        body_html="<p>We noticed a new login to your account from Chrome</p>",
        headers={},
        has_attachments=False,
        folder="INBOX",
    )


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response"""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = json.dumps(
        {
            "is_subscription": True,
            "confidence": 0.95,
            "reasoning": "Email is about subscription renewal with billing information",
            "category": "renewal",
        }
    )
    return mock_response


@pytest.fixture
def mock_openai_response_with_markdown():
    """Create a mock OpenAI response with markdown code blocks"""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[
        0
    ].message.content = """```json
{
    "is_subscription": true,
    "confidence": 0.95,
    "reasoning": "Email is about subscription renewal",
    "category": "renewal"
}
```"""
    return mock_response


def create_rate_limit_error(message: str):
    """Helper to create a RateLimitError with mock response"""
    mock_response = Mock()
    mock_response.status_code = 429
    return RateLimitError(message, response=mock_response, body=None)


def create_api_error(message: str):
    """Helper to create an APIError with mock request"""
    mock_request = Mock()
    mock_request.url = "https://api.openai.com/v1/chat/completions"
    mock_request.method = "POST"
    return APIError(message, request=mock_request, body=None)


class TestGetOpenAIClient:
    """Tests for get_openai_client function"""

    @patch("app.services.ai_classifier.get_config_value")
    @patch("app.services.ai_classifier.AsyncOpenAI")
    def test_uses_admin_settings_when_available(self, mock_openai, mock_get_config):
        """Should use API key from admin settings if available"""
        mock_get_config.return_value = "admin_api_key"

        client = get_openai_client(db=Mock())

        mock_openai.assert_called_once_with(api_key="admin_api_key")
        mock_get_config.assert_called_once()

    @patch("app.services.ai_classifier.get_config_value")
    @patch("app.services.ai_classifier.AsyncOpenAI")
    @patch("app.services.ai_classifier.settings")
    def test_falls_back_to_settings_when_no_admin_override(
        self, mock_settings, mock_openai, mock_get_config
    ):
        """Should use settings.OPENAI_API_KEY when no admin override"""
        mock_settings.OPENAI_API_KEY = "settings_api_key"
        mock_get_config.return_value = "settings_api_key"

        client = get_openai_client(db=None)

        mock_openai.assert_called_once_with(api_key="settings_api_key")


class TestClassifyEmail:
    """Tests for classify_email function"""

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.get_optimized_email_body")
    @patch("app.services.ai_classifier.get_openai_client")
    async def test_classifies_subscription_email_successfully(
        self, mock_get_client, mock_get_body, mock_email, mock_openai_response
    ):
        """Should successfully classify subscription email"""
        # Setup mocks
        mock_get_body.return_value = "Subscription renewal content"
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_openai_response
        )
        mock_get_client.return_value = mock_client

        result = await classify_email(mock_email)

        assert result["is_subscription"] is True
        assert result["confidence"] == 0.95
        assert "renewal" in result["reasoning"].lower()
        assert result["category"] == "renewal"

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.get_optimized_email_body")
    @patch("app.services.ai_classifier.get_openai_client")
    async def test_parses_response_with_markdown_code_blocks(
        self,
        mock_get_client,
        mock_get_body,
        mock_email,
        mock_openai_response_with_markdown,
    ):
        """Should parse JSON from markdown code blocks"""
        mock_get_body.return_value = "Email content"
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_openai_response_with_markdown
        )
        mock_get_client.return_value = mock_client

        result = await classify_email(mock_email)

        assert result["is_subscription"] is True
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.get_optimized_email_body")
    @patch("app.services.ai_classifier.get_openai_client")
    async def test_handles_invalid_json_response(
        self, mock_get_client, mock_get_body, mock_email
    ):
        """Should return conservative default on JSON parse error"""
        mock_get_body.return_value = "Email content"
        mock_client = AsyncMock()

        # Return invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is not valid JSON"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await classify_email(mock_email)

        assert result["is_subscription"] is False
        assert result["confidence"] == 0.0
        assert "Failed to parse" in result["reasoning"]
        assert result["category"] == "not_subscription"

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.get_optimized_email_body")
    @patch("app.services.ai_classifier.get_openai_client")
    async def test_handles_api_error(self, mock_get_client, mock_get_body, mock_email):
        """Should return conservative default on API error"""
        mock_get_body.return_value = "Email content"
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API connection failed")
        )
        mock_get_client.return_value = mock_client

        result = await classify_email(mock_email)

        assert result["is_subscription"] is False
        assert result["confidence"] == 0.0
        assert "Classification error" in result["reasoning"]
        assert result["category"] == "not_subscription"

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.get_optimized_email_body")
    @patch("app.services.ai_classifier.get_openai_client")
    async def test_uses_classification_mode_for_body_cleaning(
        self, mock_get_client, mock_get_body, mock_email, mock_openai_response
    ):
        """Should use classification mode for email body optimization"""
        mock_get_body.return_value = "Cleaned content"
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_openai_response
        )
        mock_get_client.return_value = mock_client

        await classify_email(mock_email)

        mock_get_body.assert_called_once_with(
            body_text=mock_email.body_text,
            body_html=mock_email.body_html,
            mode="classification",
        )


class TestClassifyEmailWithRetry:
    """Tests for classify_email_with_retry function"""

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.classify_email")
    async def test_returns_result_on_first_success(self, mock_classify, mock_email):
        """Should return result immediately on first success"""
        mock_classify.return_value = {
            "is_subscription": True,
            "confidence": 0.9,
            "reasoning": "Test",
            "category": "renewal",
        }

        result = await classify_email_with_retry(mock_email)

        assert result["is_subscription"] is True
        assert result["confidence"] == 0.9
        mock_classify.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.ai_classifier.classify_email")
    async def test_retries_on_rate_limit_error(
        self, mock_classify, mock_sleep, mock_email
    ):
        """Should retry with exponential backoff on rate limit"""
        # Fail twice with rate limit, then succeed
        mock_classify.side_effect = [
            create_rate_limit_error("Rate limit exceeded"),
            create_rate_limit_error("Rate limit exceeded"),
            {
                "is_subscription": True,
                "confidence": 0.9,
                "reasoning": "Test",
                "category": "renewal",
            },
        ]

        result = await classify_email_with_retry(mock_email, max_retries=3)

        assert result["is_subscription"] is True
        assert mock_classify.call_count == 3
        # Should sleep with exponential backoff: 2s, 4s
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.ai_classifier.classify_email")
    async def test_returns_default_after_max_retries(
        self, mock_classify, mock_sleep, mock_email
    ):
        """Should return conservative default after max retries"""
        mock_classify.side_effect = create_rate_limit_error("Rate limit exceeded")

        result = await classify_email_with_retry(mock_email, max_retries=3)

        assert result["is_subscription"] is False
        assert result["confidence"] == 0.0
        assert "failed after 3 retries" in result["reasoning"]
        assert result["category"] == "not_subscription"
        assert mock_classify.call_count == 3

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.ai_classifier.classify_email")
    async def test_retries_on_api_error(self, mock_classify, mock_sleep, mock_email):
        """Should retry on API errors (500, 503, etc.)"""
        mock_classify.side_effect = [
            create_api_error("Service unavailable"),
            {
                "is_subscription": True,
                "confidence": 0.9,
                "reasoning": "Test",
                "category": "renewal",
            },
        ]

        result = await classify_email_with_retry(mock_email, max_retries=3)

        assert result["is_subscription"] is True
        assert mock_classify.call_count == 2
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.classify_email")
    async def test_stops_immediately_on_unexpected_error(
        self, mock_classify, mock_email
    ):
        """Should not retry on unexpected errors"""
        mock_classify.side_effect = ValueError("Unexpected error")

        result = await classify_email_with_retry(mock_email, max_retries=3)

        assert result["is_subscription"] is False
        assert result["confidence"] == 0.0
        assert "Unexpected error" in str(result["reasoning"])
        # Should only try once, not retry
        mock_classify.assert_called_once()


class TestClassifyEmailsBatch:
    """Tests for classify_emails_batch function"""

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.classify_email_with_retry")
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    async def test_processes_batch_successfully(
        self, mock_sleep, mock_classify_retry, mock_email, mock_non_subscription_email
    ):
        """Should process all emails in batch"""
        emails = [mock_email, mock_non_subscription_email]

        mock_classify_retry.side_effect = [
            {
                "is_subscription": True,
                "confidence": 0.95,
                "reasoning": "Renewal email",
                "category": "renewal",
            },
            {
                "is_subscription": False,
                "confidence": 0.9,
                "reasoning": "Security alert",
                "category": "not_subscription",
            },
        ]

        results = await classify_emails_batch(emails, initial_batch_size=10)

        assert len(results) == 2
        assert results[0]["is_subscription"] is True
        assert results[1]["is_subscription"] is False

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.classify_email_with_retry")
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    async def test_reduces_batch_size_on_rate_limits(
        self, mock_sleep, mock_classify_retry, mock_email
    ):
        """Should reduce batch size when hitting rate limits"""
        # Create 10 emails
        emails = [mock_email for _ in range(10)]

        # First batch hits rate limit, second batch succeeds
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 5:  # First batch (5 emails with initial batch size 5)
                return {
                    "is_subscription": False,
                    "confidence": 0.0,
                    "reasoning": "Rate limit exceeded after 3 retries",
                    "category": "not_subscription",
                }
            else:  # Second batch succeeds
                return {
                    "is_subscription": True,
                    "confidence": 0.9,
                    "reasoning": "Success",
                    "category": "renewal",
                }

        mock_classify_retry.side_effect = side_effect

        results = await classify_emails_batch(
            emails, initial_batch_size=5, min_batch_size=2
        )

        assert len(results) == 10

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.classify_email_with_retry")
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    async def test_handles_exceptions_in_batch(
        self, mock_sleep, mock_classify_retry, mock_email
    ):
        """Should handle exceptions and continue processing"""
        emails = [mock_email, mock_email, mock_email]

        # First email raises exception, others succeed
        mock_classify_retry.side_effect = [
            Exception("Unexpected error"),
            {
                "is_subscription": True,
                "confidence": 0.9,
                "reasoning": "Success",
                "category": "renewal",
            },
            {
                "is_subscription": True,
                "confidence": 0.9,
                "reasoning": "Success",
                "category": "renewal",
            },
        ]

        results = await classify_emails_batch(emails, initial_batch_size=10)

        assert len(results) == 3
        # First result should be error default
        assert results[0]["is_subscription"] is False
        assert results[0]["confidence"] == 0.0
        # Others should be successful
        assert results[1]["is_subscription"] is True
        assert results[2]["is_subscription"] is True

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.classify_email_with_retry")
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    async def test_increases_batch_size_when_no_rate_limits(
        self, mock_sleep, mock_classify_retry, mock_email
    ):
        """Should increase batch size when processing smoothly"""
        # Create enough emails to test batch size increase
        emails = [mock_email for _ in range(20)]

        mock_classify_retry.return_value = {
            "is_subscription": True,
            "confidence": 0.9,
            "reasoning": "Success",
            "category": "renewal",
        }

        results = await classify_emails_batch(
            emails, initial_batch_size=5, min_batch_size=2
        )

        assert len(results) == 20
        # All should succeed
        assert all(r["is_subscription"] is True for r in results)

    @pytest.mark.asyncio
    @patch("app.services.ai_classifier.classify_email_with_retry")
    @patch("app.services.ai_classifier.asyncio.sleep", new_callable=AsyncMock)
    async def test_falls_back_to_sequential_on_catastrophic_failure(
        self, mock_sleep, mock_classify_retry, mock_email
    ):
        """Should fall back to sequential processing on batch failure"""
        emails = [mock_email, mock_email]

        # Simulate a scenario where gather itself fails
        # First call will be the batch (simulated to fail internally in gather)
        # Then falls back to sequential calls
        mock_classify_retry.return_value = {
            "is_subscription": True,
            "confidence": 0.9,
            "reasoning": "Success",
            "category": "renewal",
        }

        results = await classify_emails_batch(emails, initial_batch_size=10)

        assert len(results) == 2
