"""Comprehensive tests for cancellation research service"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4
from sqlalchemy.orm import Session
import json

from app.services.cancellation_research import (
    CancellationResearchService,
    research_cancellation,
)
from app.models.provider_cancellation import (
    ProviderCancellationInfo,
    InstructionsSource,
)


@pytest.fixture
def cancellation_service(db_session: Session) -> CancellationResearchService:
    """Create CancellationResearchService instance"""
    return CancellationResearchService(db_session)


@pytest.fixture
def sample_research_data() -> dict:
    """Sample AI research response"""
    return {
        "provider_name": "Netflix",
        "cancellation_url": "https://netflix.com/cancel",
        "difficulty": "easy",
        "instructions": [
            "Log in to netflix.com",
            "Click your profile icon",
            "Select 'Account'",
            "Click 'Cancel Membership'",
            "Confirm cancellation",
        ],
        "requires_phone": False,
        "requires_chat": False,
        "allows_pause": False,
        "pause_instructions": None,
        "additional_notes": "Access continues until end of billing period",
        "estimated_minutes": 2.0,
        "gotchas": ["No refunds for unused time"],
        "confidence": 0.9,
        "cached": False,  # Fresh research is not cached
        "researched_at": datetime.utcnow().isoformat(),
        "sources": "Official Netflix help center (2024)",
    }


@pytest.fixture
def cached_provider_info(db_session: Session) -> ProviderCancellationInfo:
    """Create cached provider cancellation info"""
    info = ProviderCancellationInfo(
        id=uuid4(),
        provider_name="Spotify",
        cancellation_url="https://spotify.com/cancel",
        difficulty_rating="medium",
        instructions=["Go to account", "Cancel subscription"],
        instructions_source=InstructionsSource.AI_GENERATED.value,
        requires_phone_call=False,
        requires_chat=False,
        allows_pause=True,
        pause_instructions=["Pause option in settings"],
        additional_notes="Can reactivate anytime",
        estimated_time_minutes=5,
        cancellation_gotchas=["Loses playlists"],
        ai_confidence_score=0.85,
        ai_research_prompt="Test prompt",
        ai_research_response=json.dumps({"test": "data"}),
        created_at=datetime.utcnow() - timedelta(days=30),
    )
    db_session.add(info)
    db_session.commit()
    db_session.refresh(info)
    return info


@pytest.fixture
def old_cached_provider(db_session: Session) -> ProviderCancellationInfo:
    """Create expired (>90 days old) cached provider info"""
    info = ProviderCancellationInfo(
        id=uuid4(),
        provider_name="Old Service",
        cancellation_url="https://old.com/cancel",
        difficulty_rating="hard",
        instructions=["Call support"],
        instructions_source=InstructionsSource.AI_GENERATED.value,
        requires_phone_call=True,
        requires_chat=False,
        ai_confidence_score=0.7,
        created_at=datetime.utcnow() - timedelta(days=100),
    )
    db_session.add(info)
    db_session.commit()
    db_session.refresh(info)
    return info


class TestCancellationResearchServiceInit:
    """Tests for service initialization"""

    def test_initializes_with_db_session(self, db_session: Session):
        """Should initialize with database session"""
        service = CancellationResearchService(db_session)

        assert service.db == db_session
        assert service.client is None  # Lazy initialization

    def test_get_client_lazy_initialization(
        self, cancellation_service: CancellationResearchService
    ):
        """Should lazily initialize OpenAI client"""
        with patch(
            "app.services.cancellation_research.get_openai_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            client1 = cancellation_service._get_client()
            client2 = cancellation_service._get_client()

            assert client1 == mock_client
            assert client2 == mock_client
            mock_get_client.assert_called_once()  # Only called once


class TestResearchProvider:
    """Tests for research_provider method"""

    @pytest.mark.asyncio
    async def test_rejects_empty_provider_name(
        self, cancellation_service: CancellationResearchService
    ):
        """Should raise ValueError for empty provider name"""
        with pytest.raises(ValueError, match="provider_name cannot be empty"):
            await cancellation_service.research_provider("")

    @pytest.mark.asyncio
    async def test_rejects_whitespace_provider_name(
        self, cancellation_service: CancellationResearchService
    ):
        """Should raise ValueError for whitespace-only provider name"""
        with pytest.raises(ValueError, match="provider_name cannot be empty"):
            await cancellation_service.research_provider("   ")

    @pytest.mark.asyncio
    async def test_returns_cached_result_when_available(
        self,
        cancellation_service: CancellationResearchService,
        cached_provider_info: ProviderCancellationInfo,
    ):
        """Should return cached result without calling API"""
        result = await cancellation_service.research_provider("Spotify")

        assert result["provider_name"] == "Spotify"
        assert result["cached"] is True
        assert result["difficulty"] == "medium"
        assert result["cancellation_url"] == "https://spotify.com/cancel"
        assert "cached_at" in result

    @pytest.mark.asyncio
    async def test_refreshes_expired_cache(
        self,
        cancellation_service: CancellationResearchService,
        old_cached_provider: ProviderCancellationInfo,
        sample_research_data: dict,
    ):
        """Should refresh cache when >90 days old"""
        with patch.object(
            cancellation_service,
            "_call_openai_research",
            new=AsyncMock(return_value=sample_research_data),
        ):
            result = await cancellation_service.research_provider("Old Service")

            # Should get fresh research, not cached
            assert result["cached"] is False
            assert result["provider_name"] == "Netflix"  # From sample data

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self,
        cancellation_service: CancellationResearchService,
        cached_provider_info: ProviderCancellationInfo,
        sample_research_data: dict,
    ):
        """Should bypass cache when force_refresh=True"""
        with patch.object(
            cancellation_service,
            "_call_openai_research",
            new=AsyncMock(return_value=sample_research_data),
        ):
            result = await cancellation_service.research_provider(
                "Spotify", force_refresh=True
            )

            assert result["cached"] is False
            assert result["provider_name"] == "Netflix"

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(
        self, cancellation_service: CancellationResearchService
    ):
        """Should propagate RateLimitError"""
        from openai import RateLimitError

        with patch.object(
            cancellation_service,
            "_call_openai_research",
            new=AsyncMock(
                side_effect=RateLimitError(
                    message="Rate limit exceeded", response=MagicMock(), body=None
                )
            ),
        ):
            with pytest.raises(RateLimitError):
                await cancellation_service.research_provider("Test Service")

    @pytest.mark.asyncio
    async def test_handles_api_error(
        self, cancellation_service: CancellationResearchService
    ):
        """Should propagate APIError"""
        from openai import APIError

        with patch.object(
            cancellation_service,
            "_call_openai_research",
            new=AsyncMock(
                side_effect=APIError(
                    message="API error", request=MagicMock(), body=None
                )
            ),
        ):
            with pytest.raises(APIError):
                await cancellation_service.research_provider("Test Service")


class TestGetCachedResearch:
    """Tests for _get_cached_research method"""

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_provider(
        self, cancellation_service: CancellationResearchService
    ):
        """Should return None if provider not in cache"""
        result = await cancellation_service._get_cached_research("Nonexistent Service")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_cached_provider_info(
        self,
        cancellation_service: CancellationResearchService,
        cached_provider_info: ProviderCancellationInfo,
    ):
        """Should return cached provider info in correct format"""
        result = await cancellation_service._get_cached_research("Spotify")

        assert result is not None
        assert result["provider_name"] == "Spotify"
        assert result["difficulty"] == "medium"
        assert result["cached"] is True
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_case_insensitive_lookup(
        self,
        cancellation_service: CancellationResearchService,
        cached_provider_info: ProviderCancellationInfo,
    ):
        """Should find provider with case-insensitive search"""
        result = await cancellation_service._get_cached_research("spotify")

        assert result is not None
        assert result["provider_name"] == "Spotify"

    @pytest.mark.asyncio
    async def test_returns_none_for_old_cache(
        self,
        cancellation_service: CancellationResearchService,
        old_cached_provider: ProviderCancellationInfo,
    ):
        """Should return None for cache older than 90 days"""
        result = await cancellation_service._get_cached_research("Old Service")

        assert result is None


class TestCallOpenAIResearch:
    """Tests for _call_openai_research method"""

    @pytest.mark.asyncio
    async def test_calls_openai_with_correct_parameters(
        self,
        cancellation_service: CancellationResearchService,
        sample_research_data: dict,
    ):
        """Should call OpenAI API with correct parameters"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(sample_research_data)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(
            cancellation_service, "_get_client", return_value=mock_client
        ):
            with patch(
                "app.services.cancellation_research.validate_research"
            ) as mock_validate:
                mock_validate.return_value = {
                    "is_valid": True,
                    "warnings": [],
                    "quality_score": 0.9,
                    "recommended_action": "accept",
                }

                await cancellation_service._call_openai_research("Netflix")

                # Verify OpenAI was called
                mock_client.chat.completions.create.assert_called_once()
                call_kwargs = mock_client.chat.completions.create.call_args[1]

                assert call_kwargs["model"] == "gpt-4o-mini"
                assert call_kwargs["temperature"] == 0.3
                assert call_kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_parses_json_response_correctly(
        self,
        cancellation_service: CancellationResearchService,
        sample_research_data: dict,
    ):
        """Should parse and return JSON response"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(sample_research_data)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(
            cancellation_service, "_get_client", return_value=mock_client
        ):
            with patch(
                "app.services.cancellation_research.validate_research"
            ) as mock_validate:
                mock_validate.return_value = {
                    "is_valid": True,
                    "warnings": [],
                    "quality_score": 0.9,
                    "recommended_action": "accept",
                }

                result = await cancellation_service._call_openai_research("Netflix")

                assert result["provider_name"] == "Netflix"
                assert result["difficulty"] == "easy"
                assert result["cached"] is False
                assert "researched_at" in result
                assert "validation" in result

    @pytest.mark.asyncio
    async def test_validates_required_fields(
        self, cancellation_service: CancellationResearchService
    ):
        """Should raise ValueError for missing required fields"""
        incomplete_data = {
            "difficulty": "easy",
            # Missing other required fields
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(incomplete_data)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(
            cancellation_service, "_get_client", return_value=mock_client
        ):
            with pytest.raises(ValueError, match="Missing required field"):
                await cancellation_service._call_openai_research("Netflix")

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(
        self, cancellation_service: CancellationResearchService
    ):
        """Should raise ValueError for invalid JSON"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Not valid JSON"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(
            cancellation_service, "_get_client", return_value=mock_client
        ):
            with pytest.raises(ValueError, match="Invalid JSON response"):
                await cancellation_service._call_openai_research("Netflix")

    @pytest.mark.asyncio
    async def test_integrates_with_validation_service(
        self,
        cancellation_service: CancellationResearchService,
        sample_research_data: dict,
    ):
        """Should call validation service and include results"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(sample_research_data)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_validation = {
            "is_valid": True,
            "warnings": [],
            "quality_score": 0.95,
            "recommended_action": "accept",
        }

        with patch.object(
            cancellation_service, "_get_client", return_value=mock_client
        ):
            with patch(
                "app.services.cancellation_research.validate_research"
            ) as mock_validate:
                mock_validate.return_value = mock_validation

                result = await cancellation_service._call_openai_research("Netflix")

                mock_validate.assert_called_once()
                assert result["validation"] == mock_validation


class TestStoreResearchResult:
    """Tests for _store_research_result method"""

    @pytest.mark.asyncio
    async def test_creates_new_provider_info(
        self,
        cancellation_service: CancellationResearchService,
        sample_research_data: dict,
    ):
        """Should create new ProviderCancellationInfo record"""
        with patch(
            "app.services.cancellation_research.validate_research"
        ) as mock_validate:
            mock_validate.return_value = {
                "quality_score": 0.9,
                "recommended_action": "accept",
                "warning_count": {"high": 0, "medium": 0, "low": 0},
            }

            # Add validation to research data
            sample_research_data["validation"] = mock_validate.return_value
            sample_research_data["prompt_version"] = "v2_enhanced"

            result = await cancellation_service._store_research_result(
                "Netflix", sample_research_data
            )

            assert result.provider_name == "Netflix"
            assert result.difficulty_rating == "easy"
            assert result.cancellation_url == "https://netflix.com/cancel"
            assert result.requires_phone_call is False
            assert result.ai_confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_updates_existing_provider_info(
        self,
        cancellation_service: CancellationResearchService,
        cached_provider_info: ProviderCancellationInfo,
        sample_research_data: dict,
    ):
        """Should update existing ProviderCancellationInfo record"""
        with patch(
            "app.services.cancellation_research.validate_research"
        ) as mock_validate:
            mock_validate.return_value = {
                "quality_score": 0.9,
                "recommended_action": "accept",
                "warning_count": {"high": 0, "medium": 0, "low": 0},
            }

            sample_research_data["validation"] = mock_validate.return_value
            sample_research_data["prompt_version"] = "v2_enhanced"
            sample_research_data["provider_name"] = "Spotify"  # Update existing
            sample_research_data["difficulty"] = "hard"  # Change difficulty

            result = await cancellation_service._store_research_result(
                "Spotify", sample_research_data
            )

            assert result.provider_name == "Spotify"
            assert result.difficulty_rating == "hard"
            assert result.id == cached_provider_info.id  # Same record

    @pytest.mark.asyncio
    async def test_handles_invalid_difficulty_gracefully(
        self,
        cancellation_service: CancellationResearchService,
        sample_research_data: dict,
    ):
        """Should default to 'medium' for invalid difficulty"""
        with patch(
            "app.services.cancellation_research.validate_research"
        ) as mock_validate:
            mock_validate.return_value = {
                "quality_score": 0.9,
                "recommended_action": "accept",
                "warning_count": {"high": 0, "medium": 0, "low": 0},
            }

            sample_research_data["validation"] = mock_validate.return_value
            sample_research_data["prompt_version"] = "v2_enhanced"
            sample_research_data["difficulty"] = "INVALID"

            result = await cancellation_service._store_research_result(
                "Test Service", sample_research_data
            )

            assert result.difficulty_rating == "medium"


class TestResearchCancellationConvenienceFunction:
    """Tests for research_cancellation convenience function"""

    @pytest.mark.asyncio
    async def test_convenience_function_works(
        self, db_session: Session, cached_provider_info: ProviderCancellationInfo
    ):
        """Should work through convenience function"""
        result = await research_cancellation("Spotify", db_session)

        assert result["provider_name"] == "Spotify"
        assert result["cached"] is True

    @pytest.mark.asyncio
    async def test_convenience_function_with_force_refresh(
        self,
        db_session: Session,
        cached_provider_info: ProviderCancellationInfo,
        sample_research_data: dict,
    ):
        """Should support force_refresh parameter"""
        with patch(
            "app.services.cancellation_research.CancellationResearchService._call_openai_research"
        ) as mock_research:
            mock_research.return_value = sample_research_data

            await research_cancellation(
                "Spotify", db_session, force_refresh=True
            )

            # Should call OpenAI even with cache present
            mock_research.assert_called_once()
