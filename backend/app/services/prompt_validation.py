"""
AI response validation framework for cancellation research quality assurance.
"""

from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ValidationWarning:
    """Represents a quality warning in AI research results"""

    def __init__(self, severity: str, message: str, field: str = None):
        self.severity = severity  # "low", "medium", "high"
        self.message = message
        self.field = field

    def to_dict(self) -> Dict[str, Any]:
        return {"severity": self.severity, "message": self.message, "field": self.field}


class ResearchValidator:
    """Validates AI-generated cancellation research for quality and consistency"""

    def __init__(self):
        self.vague_terms = [
            "settings",
            "account",
            "profile",
            "manage",
            "dashboard",
            "menu",
            "options",
            "preferences",
            "page",
            "section",
        ]

    def validate(self, research_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive validation of research results.

        Args:
            research_data: Research results from AI

        Returns:
            Validation report with warnings and quality metrics
        """
        warnings: List[ValidationWarning] = []

        # Run all validation checks
        warnings.extend(self._check_confidence_alignment(research_data))
        warnings.extend(self._check_instruction_quality(research_data))
        warnings.extend(self._check_url_validity(research_data))
        warnings.extend(self._check_logical_consistency(research_data))
        warnings.extend(self._check_source_quality(research_data))
        warnings.extend(self._check_completeness(research_data))

        # Calculate overall quality score
        quality_score = self._calculate_quality_score(warnings, research_data)

        # Determine recommended action
        action = self._recommend_action(warnings, quality_score)

        report = {
            "is_valid": len([w for w in warnings if w.severity == "high"]) == 0,
            "warnings": [w.to_dict() for w in warnings],
            "warning_count": {
                "high": len([w for w in warnings if w.severity == "high"]),
                "medium": len([w for w in warnings if w.severity == "medium"]),
                "low": len([w for w in warnings if w.severity == "low"]),
            },
            "quality_score": quality_score,
            "recommended_action": action,
            "validation_timestamp": datetime.utcnow().isoformat(),
        }

        # Log validation results
        if warnings:
            logger.warning(
                f"Validation found {len(warnings)} issues for {research_data.get('provider_name', 'unknown')}: "
                f"quality_score={quality_score:.2f}, action={action}"
            )
        else:
            logger.info(
                f"Validation passed for {research_data.get('provider_name', 'unknown')}: "
                f"quality_score={quality_score:.2f}"
            )

        return report

    def _check_confidence_alignment(
        self, data: Dict[str, Any]
    ) -> List[ValidationWarning]:
        """Check if confidence score aligns with data completeness"""
        warnings = []
        confidence = data.get("confidence", 0.0)

        # High confidence without URL
        if confidence > 0.8:
            if not data.get("cancellation_url"):
                warnings.append(
                    ValidationWarning(
                        severity="medium",
                        message="High confidence (>0.8) but missing cancellation URL",
                        field="cancellation_url",
                    )
                )

            # High confidence without sources (v2 format)
            sources = data.get("sources")
            if isinstance(sources, dict):
                if not sources.get("primary_source"):
                    warnings.append(
                        ValidationWarning(
                            severity="medium",
                            message="High confidence but no source information provided",
                            field="sources",
                        )
                    )

                # Check source recency for high confidence
                primary_source = sources.get("primary_source", "")
                if "2024" not in primary_source and "2025" not in primary_source:
                    warnings.append(
                        ValidationWarning(
                            severity="medium",
                            message="High confidence but sources not from 2024-2025",
                            field="sources",
                        )
                    )
            elif isinstance(sources, str):
                # v1 format - check for year mentions
                if not sources or ("2024" not in sources and "2025" not in sources):
                    warnings.append(
                        ValidationWarning(
                            severity="low",
                            message="High confidence but sources not explicitly from 2024-2025",
                            field="sources",
                        )
                    )

        # Low confidence with detailed instructions
        if confidence < 0.4:
            instructions = data.get("instructions", [])
            if len(instructions) > 5:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="Low confidence (<0.4) but detailed instructions provided - verify alignment",
                        field="confidence",
                    )
                )

        return warnings

    def _check_instruction_quality(
        self, data: Dict[str, Any]
    ) -> List[ValidationWarning]:
        """Check if instructions are specific and actionable"""
        warnings = []
        instructions = data.get("instructions", [])

        if not instructions:
            warnings.append(
                ValidationWarning(
                    severity="high",
                    message="No cancellation instructions provided",
                    field="instructions",
                )
            )
            return warnings

        # Check for vague instructions
        vague_count = 0
        for instruction in instructions:
            if isinstance(instruction, str):
                # Check if instruction is mostly vague terms
                words = instruction.lower().split()
                vague_words = [w for w in words if w in self.vague_terms]
                if len(vague_words) / max(len(words), 1) > 0.5:
                    vague_count += 1

        vague_ratio = vague_count / len(instructions)
        if vague_ratio > 0.6:
            warnings.append(
                ValidationWarning(
                    severity="medium",
                    message=f"Instructions may be too generic ({vague_ratio:.0%} vague steps)",
                    field="instructions",
                )
            )
        elif vague_ratio > 0.4:
            warnings.append(
                ValidationWarning(
                    severity="low",
                    message=f"Some instructions lack specificity ({vague_ratio:.0%} vague steps)",
                    field="instructions",
                )
            )

        # Check instruction length
        avg_length = sum(len(str(i)) for i in instructions) / len(instructions)
        if avg_length < 20:
            warnings.append(
                ValidationWarning(
                    severity="low",
                    message="Instructions are very brief - may lack necessary detail",
                    field="instructions",
                )
            )

        # Check for numbered/ordered clarity
        has_navigation = any(
            word in str(instruction).lower()
            for instruction in instructions
            for word in ["click", "select", "go to", "navigate", "tap", "press"]
        )
        if not has_navigation and len(instructions) > 2:
            warnings.append(
                ValidationWarning(
                    severity="low",
                    message="Instructions lack clear navigation verbs (click, select, etc.)",
                    field="instructions",
                )
            )

        return warnings

    def _check_url_validity(self, data: Dict[str, Any]) -> List[ValidationWarning]:
        """Check if provided URLs appear valid"""
        warnings = []
        url = data.get("cancellation_url")

        if url:
            # Basic URL format check
            if not url.startswith(("http://", "https://")):
                warnings.append(
                    ValidationWarning(
                        severity="high",
                        message="Cancellation URL does not start with http:// or https://",
                        field="cancellation_url",
                    )
                )

            # Check for common issues
            if " " in url:
                warnings.append(
                    ValidationWarning(
                        severity="high",
                        message="Cancellation URL contains spaces",
                        field="cancellation_url",
                    )
                )

            # Check for incomplete URLs
            if url.count("/") < 3:  # Should have at least https://domain.com/path
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="Cancellation URL may be incomplete (missing path)",
                        field="cancellation_url",
                    )
                )

        return warnings

    def _check_logical_consistency(
        self, data: Dict[str, Any]
    ) -> List[ValidationWarning]:
        """Check for logical inconsistencies in the data"""
        warnings = []

        difficulty = data.get("difficulty", "").lower()
        requires_phone = data.get("requires_phone", False)
        requires_chat = data.get("requires_chat", False)
        cancellation_url = data.get("cancellation_url")
        estimated_minutes = data.get("estimated_minutes")

        # Easy difficulty but requires phone/chat
        if difficulty == "easy":
            if requires_phone:
                warnings.append(
                    ValidationWarning(
                        severity="medium",
                        message="Marked as 'easy' but requires phone call - inconsistency detected",
                        field="difficulty",
                    )
                )
            if requires_chat:
                warnings.append(
                    ValidationWarning(
                        severity="medium",
                        message="Marked as 'easy' but requires live chat - inconsistency detected",
                        field="difficulty",
                    )
                )

        # Hard difficulty but has simple URL
        if difficulty == "hard" and cancellation_url:
            if not requires_phone and not requires_chat:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="Marked as 'hard' with URL but doesn't require phone/chat - verify complexity",
                        field="difficulty",
                    )
                )

        # Time estimation alignment
        if estimated_minutes:
            if difficulty == "easy" and estimated_minutes > 5:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="'Easy' difficulty but estimated >5 minutes - verify alignment",
                        field="estimated_minutes",
                    )
                )
            if difficulty == "hard" and estimated_minutes < 10:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="'Hard' difficulty but estimated <10 minutes - verify alignment",
                        field="estimated_minutes",
                    )
                )

        # Pause instructions without allows_pause
        if data.get("pause_instructions") and not data.get("allows_pause"):
            warnings.append(
                ValidationWarning(
                    severity="medium",
                    message="Pause instructions provided but allows_pause is false",
                    field="allows_pause",
                )
            )

        return warnings

    def _check_source_quality(self, data: Dict[str, Any]) -> List[ValidationWarning]:
        """Check quality and structure of source attribution"""
        warnings = []
        sources = data.get("sources")
        confidence = data.get("confidence", 0.0)

        if not sources:
            if confidence > 0.5:
                warnings.append(
                    ValidationWarning(
                        severity="medium",
                        message="Moderate-high confidence but no sources provided",
                        field="sources",
                    )
                )
            return warnings

        # V2 structured sources
        if isinstance(sources, dict):
            primary_type = sources.get("primary_source_type")
            primary_source = sources.get("primary_source")
            verification = sources.get("verification")

            # Check source type alignment with confidence
            if primary_type == "official_documentation" and confidence < 0.7:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="Official documentation cited but confidence <0.7 - verify alignment",
                        field="confidence",
                    )
                )

            if primary_type in ["speculation", "mixed"] and confidence > 0.6:
                warnings.append(
                    ValidationWarning(
                        severity="medium",
                        message="Speculation/mixed sources but confidence >0.6 - may be overconfident",
                        field="confidence",
                    )
                )

            # Check for missing structured fields
            if not primary_source:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="Source structure present but missing primary_source description",
                        field="sources",
                    )
                )

            if not verification and confidence > 0.7:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="High confidence but missing verification details",
                        field="sources",
                    )
                )

        # V1 string sources
        elif isinstance(sources, str):
            if len(sources) < 20:
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="Source description is very brief - may lack detail",
                        field="sources",
                    )
                )

        return warnings

    def _check_completeness(self, data: Dict[str, Any]) -> List[ValidationWarning]:
        """Check for missing or null important fields"""
        warnings = []

        # Critical fields
        if not data.get("difficulty"):
            warnings.append(
                ValidationWarning(
                    severity="high",
                    message="Missing required field: difficulty",
                    field="difficulty",
                )
            )

        if not data.get("instructions"):
            warnings.append(
                ValidationWarning(
                    severity="high",
                    message="Missing required field: instructions",
                    field="instructions",
                )
            )

        # Important optional fields for completeness
        confidence = data.get("confidence", 0.0)
        if confidence > 0.7:
            # For high-confidence results, expect more complete data
            if not data.get("estimated_minutes"):
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="High confidence but missing time estimate",
                        field="estimated_minutes",
                    )
                )

            if not data.get("gotchas"):
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="High confidence but no gotchas/warnings provided",
                        field="gotchas",
                    )
                )

            if not data.get("additional_notes"):
                warnings.append(
                    ValidationWarning(
                        severity="low",
                        message="High confidence but no additional notes provided",
                        field="additional_notes",
                    )
                )

        return warnings

    def _calculate_quality_score(
        self, warnings: List[ValidationWarning], data: Dict[str, Any]
    ) -> float:
        """
        Calculate overall quality score (0.0 to 1.0).

        Factors:
        - Warnings (penalize by severity)
        - Confidence score
        - Completeness
        - Specificity
        """
        score = 1.0

        # Penalize for warnings
        for warning in warnings:
            if warning.severity == "high":
                score -= 0.20
            elif warning.severity == "medium":
                score -= 0.10
            elif warning.severity == "low":
                score -= 0.05

        # Bonus for completeness
        optional_fields = [
            "cancellation_url",
            "estimated_minutes",
            "gotchas",
            "additional_notes",
            "pause_instructions",
        ]
        filled_count = sum(1 for field in optional_fields if data.get(field))
        completeness_bonus = (filled_count / len(optional_fields)) * 0.15
        score += completeness_bonus

        # Ensure score is in valid range
        return max(0.0, min(1.0, score))

    def _recommend_action(
        self, warnings: List[ValidationWarning], quality_score: float
    ) -> str:
        """
        Recommend action based on validation results.

        Returns: "accept", "review", or "regenerate"
        """
        high_warnings = [w for w in warnings if w.severity == "high"]
        medium_warnings = [w for w in warnings if w.severity == "medium"]

        if len(high_warnings) > 0:
            return "regenerate"

        if quality_score < 0.6:
            return "regenerate"

        if len(medium_warnings) > 2:
            return "review"

        if quality_score < 0.75:
            return "review"

        return "accept"


def validate_research(research_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to validate research results.

    Args:
        research_data: Research results from AI

    Returns:
        Validation report
    """
    validator = ResearchValidator()
    return validator.validate(research_data)
