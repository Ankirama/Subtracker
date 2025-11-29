"""Tests for prompt_validation service"""

import pytest
from app.services.prompt_validation import (
    ValidationWarning,
    ResearchValidator,
    validate_research,
)


class TestValidationWarning:
    """Tests for ValidationWarning class"""

    def test_creates_warning_with_all_fields(self):
        """Should create warning with severity, message, and field"""
        warning = ValidationWarning(
            severity="high", message="Test warning", field="test_field"
        )

        assert warning.severity == "high"
        assert warning.message == "Test warning"
        assert warning.field == "test_field"

    def test_creates_warning_without_field(self):
        """Should create warning without field specified"""
        warning = ValidationWarning(severity="low", message="Test")

        assert warning.severity == "low"
        assert warning.message == "Test"
        assert warning.field is None

    def test_to_dict_conversion(self):
        """Should convert warning to dictionary"""
        warning = ValidationWarning("medium", "Test message", "field_name")
        result = warning.to_dict()

        assert result == {
            "severity": "medium",
            "message": "Test message",
            "field": "field_name",
        }


class TestResearchValidator:
    """Tests for ResearchValidator class"""

    @pytest.fixture
    def validator(self):
        """Create validator instance"""
        return ResearchValidator()

    def test_validates_perfect_research(self, validator):
        """Should pass validation for high-quality research"""
        research = {
            "provider_name": "Netflix",
            "confidence": 0.9,
            "difficulty": "easy",
            "cancellation_url": "https://netflix.com/cancel",
            "instructions": [
                "Click on your profile icon",
                "Select 'Account Settings'",
                "Navigate to 'Membership & Billing'",
                "Click 'Cancel Membership'",
            ],
            "estimated_minutes": 3,
            "requires_phone": False,
            "requires_chat": False,
            "allows_pause": True,
            "pause_instructions": "Select pause option",
            "gotchas": ["Must cancel 24 hours before renewal"],
            "additional_notes": "Process is straightforward",
            "sources": {
                "primary_source_type": "official_documentation",
                "primary_source": "Netflix Help Center, accessed 2024-11-15",
                "verification": "Tested on 2024-11-15",
            },
        }

        result = validator.validate(research)

        assert result["is_valid"] is True
        assert result["warning_count"]["high"] == 0
        assert result["quality_score"] > 0.8
        assert result["recommended_action"] == "accept"

    def test_detects_high_confidence_without_url(self, validator):
        """Should warn when high confidence but missing cancellation URL"""
        research = {
            "provider_name": "Test",
            "confidence": 0.9,
            "difficulty": "easy",
            "instructions": ["Step 1", "Step 2"],
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any(
            w["severity"] == "medium" and "missing cancellation URL" in w["message"]
            for w in warnings
        )

    def test_detects_high_confidence_without_recent_sources(self, validator):
        """Should warn when high confidence but sources not from 2024-2025"""
        research = {
            "provider_name": "Test",
            "confidence": 0.9,
            "difficulty": "easy",
            "instructions": ["Step 1"],
            "cancellation_url": "https://example.com/cancel",
            "sources": {"primary_source": "Old documentation from 2022"},
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any("2024-2025" in w["message"] for w in warnings)

    def test_detects_missing_instructions(self, validator):
        """Should error when no instructions provided"""
        research = {"provider_name": "Test", "confidence": 0.5, "difficulty": "medium"}

        result = validator.validate(research)

        assert result["is_valid"] is False
        warnings = result["warnings"]
        assert any(
            w["severity"] == "high" and "No cancellation instructions" in w["message"]
            for w in warnings
        )

    def test_detects_vague_instructions(self, validator):
        """Should warn when instructions are too generic"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "difficulty": "medium",
            "instructions": [
                "Go to settings menu",  # 4 words, 2 vague (settings, menu) = 50%
                "Find account profile",  # 3 words, 2 vague (account, profile) = 67%
                "Open dashboard page",  # 3 words, 2 vague (dashboard, page) = 67%
                "Check options preferences",  # 3 words, 2 vague (options, preferences) = 67%
                "Manage account settings",  # 3 words, 3 vague (manage, account, settings) = 100%
            ],
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        # Should detect vague instructions (4 out of 5 are >50% vague = 80% ratio)
        assert any("generic" in w["message"].lower() for w in warnings)

    def test_detects_brief_instructions(self, validator):
        """Should warn when instructions are too brief"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "difficulty": "medium",
            "instructions": ["Go", "Click", "Done"],
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any("very brief" in w["message"] for w in warnings)

    def test_detects_invalid_url_format(self, validator):
        """Should error on invalid URL format"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "difficulty": "medium",
            "instructions": ["Step 1"],
            "cancellation_url": "not-a-valid-url",
        }

        result = validator.validate(research)

        assert result["is_valid"] is False
        warnings = result["warnings"]
        assert any(
            w["severity"] == "high" and "does not start with http" in w["message"]
            for w in warnings
        )

    def test_detects_url_with_spaces(self, validator):
        """Should error on URL with spaces"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "difficulty": "medium",
            "instructions": ["Step 1"],
            "cancellation_url": "https://example.com/path with spaces",
        }

        result = validator.validate(research)

        assert result["is_valid"] is False
        warnings = result["warnings"]
        assert any(
            w["severity"] == "high" and "contains spaces" in w["message"]
            for w in warnings
        )

    def test_detects_easy_difficulty_with_phone_requirement(self, validator):
        """Should warn when marked easy but requires phone"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "difficulty": "easy",
            "requires_phone": True,
            "instructions": ["Call support"],
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any("'easy' but requires phone" in w["message"] for w in warnings)

    def test_detects_time_estimation_misalignment(self, validator):
        """Should warn when difficulty doesn't match time estimate"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "difficulty": "easy",
            "estimated_minutes": 20,  # Too long for "easy"
            "instructions": ["Step 1", "Step 2"],
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any(
            "'Easy' difficulty but estimated >5 minutes" in w["message"]
            for w in warnings
        )

    def test_detects_pause_instruction_without_allows_pause(self, validator):
        """Should warn when pause_instructions exist but allows_pause is false"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "difficulty": "medium",
            "instructions": ["Step 1"],
            "allows_pause": False,
            "pause_instructions": "Click pause button",
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any(
            "Pause instructions provided but allows_pause is false" in w["message"]
            for w in warnings
        )

    def test_detects_missing_sources_with_confidence(self, validator):
        """Should warn when moderate confidence but no sources"""
        research = {
            "provider_name": "Test",
            "confidence": 0.7,
            "difficulty": "medium",
            "instructions": ["Step 1"],
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any("confidence but no sources" in w["message"] for w in warnings)

    def test_detects_speculation_with_high_confidence(self, validator):
        """Should warn when speculation/mixed sources have high confidence"""
        research = {
            "provider_name": "Test",
            "confidence": 0.8,
            "difficulty": "medium",
            "instructions": ["Step 1"],
            "cancellation_url": "https://example.com/cancel",
            "sources": {
                "primary_source_type": "speculation",
                "primary_source": "Based on user reports from 2024",
            },
        }

        result = validator.validate(research)

        warnings = result["warnings"]
        assert any(
            "Speculation" in w["message"] and "overconfident" in w["message"]
            for w in warnings
        )

    def test_detects_missing_difficulty(self, validator):
        """Should error when difficulty field is missing"""
        research = {
            "provider_name": "Test",
            "confidence": 0.5,
            "instructions": ["Step 1"],
        }

        result = validator.validate(research)

        assert result["is_valid"] is False
        warnings = result["warnings"]
        assert any(
            w["severity"] == "high"
            and "Missing required field: difficulty" in w["message"]
            for w in warnings
        )

    def test_calculates_quality_score(self, validator):
        """Should calculate quality score based on completeness and warnings"""
        # High quality research
        good_research = {
            "provider_name": "Test",
            "confidence": 0.8,
            "difficulty": "easy",
            "instructions": ["Click account settings", "Select cancel membership"],
            "cancellation_url": "https://example.com/cancel",
            "estimated_minutes": 3,
            "gotchas": ["Must cancel before renewal"],
            "additional_notes": "Simple process",
            "pause_instructions": "Select pause option",
            "sources": {
                "primary_source_type": "official_documentation",
                "primary_source": "Official docs 2024",
            },
        }

        result = validator.validate(good_research)
        assert result["quality_score"] > 0.8

        # Low quality research
        poor_research = {
            "confidence": 0.3,
            "instructions": ["Go to settings", "Click menu", "Find option"],
            # Missing: provider_name, difficulty (HIGH), cancellation_url, sources
            # Has: brief instructions (LOW)
            # Score: 1.0 - 0.20 (HIGH) - 0.05 (LOW) = 0.75
        }

        result = validator.validate(poor_research)
        assert result["quality_score"] < 0.8

    def test_recommends_regenerate_for_high_warnings(self, validator):
        """Should recommend regenerate when high severity warnings exist"""
        research = {
            "confidence": 0.5,
            "cancellation_url": "not-a-url",  # Will trigger high severity warning
        }

        result = validator.validate(research)
        assert result["recommended_action"] == "regenerate"

    def test_recommends_review_for_medium_warnings(self, validator):
        """Should recommend review when multiple medium warnings"""
        research = {
            "provider_name": "Test",
            "confidence": 0.9,  # High confidence triggers checks
            "difficulty": "easy",
            "requires_phone": True,  # Inconsistent with easy - medium warning
            "instructions": ["Step 1"],
            # Missing URL - another medium warning
            # Missing recent sources - another warning
        }

        result = validator.validate(research)
        assert result["recommended_action"] in ["review", "regenerate"]

    def test_recommends_accept_for_good_quality(self, validator):
        """Should recommend accept for high quality research"""
        research = {
            "provider_name": "Netflix",
            "confidence": 0.85,
            "difficulty": "easy",
            "cancellation_url": "https://netflix.com/cancel",
            "instructions": [
                "Navigate to account settings",
                "Select membership and billing",
                "Click cancel membership",
                "Confirm cancellation",
            ],
            "estimated_minutes": 3,
            "requires_phone": False,
            "gotchas": ["Must cancel before billing date"],
            "additional_notes": "Immediate effect",
            "sources": {
                "primary_source_type": "official_documentation",
                "primary_source": "Netflix Help Center 2024",
                "verification": "Tested 2024-11-15",
            },
        }

        result = validator.validate(research)
        assert result["recommended_action"] == "accept"
        assert result["quality_score"] > 0.75


def test_validate_research_convenience_function():
    """Should work through convenience function"""
    research = {
        "provider_name": "Test",
        "confidence": 0.6,
        "difficulty": "medium",
        "instructions": ["Navigate to settings", "Click cancel account"],
        "cancellation_url": "https://example.com/cancel",
    }

    result = validate_research(research)

    assert "is_valid" in result
    assert "warnings" in result
    assert "quality_score" in result
    assert "recommended_action" in result
    assert "validation_timestamp" in result
