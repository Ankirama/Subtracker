"""
Pydantic schemas for cancellation feedback.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class FeedbackSubmission(BaseModel):
    """Schema for submitting feedback on cancellation instructions"""

    provider_cancellation_id: UUID = Field(
        ..., description="ID of the provider cancellation info"
    )
    feedback_type: str = Field(
        ...,
        description="Type of feedback: helpful, not_helpful, inaccurate, incomplete, worked, failed",
    )

    # Success tracking
    successfully_cancelled: Optional[bool] = Field(
        None, description="Did the user successfully cancel?"
    )
    time_taken_minutes: Optional[int] = Field(
        None, ge=0, le=240, description="Time taken in minutes (0-240)"
    )

    # Ratings
    helpfulness_rating: Optional[int] = Field(
        None, ge=1, le=5, description="Helpfulness rating (1-5)"
    )
    accuracy_rating: Optional[int] = Field(
        None, ge=1, le=5, description="Accuracy rating (1-5)"
    )

    # Details
    comment: Optional[str] = Field(
        None, max_length=2000, description="Optional written feedback"
    )
    issues_encountered: Optional[List[str]] = Field(
        None, description="List of issues encountered"
    )

    device_type: Optional[str] = Field(
        None, description="Device type: web, mobile, tablet"
    )

    @validator("feedback_type")
    def validate_feedback_type(cls, v):
        valid_types = [
            "helpful",
            "not_helpful",
            "inaccurate",
            "incomplete",
            "worked",
            "failed",
        ]
        if v not in valid_types:
            raise ValueError(f"feedback_type must be one of {valid_types}")
        return v

    @validator("issues_encountered")
    def validate_issues(cls, v):
        if v is None:
            return v
        valid_issues = [
            "incorrect_url",
            "missing_steps",
            "outdated_info",
            "requires_phone",
            "requires_chat",
            "confusing_instructions",
            "took_too_long",
            "other",
        ]
        for issue in v:
            if issue not in valid_issues:
                raise ValueError(
                    f"Invalid issue: {issue}. Must be one of {valid_issues}"
                )
        return v


class FeedbackResponse(BaseModel):
    """Response schema for feedback"""

    id: UUID
    user_id: UUID
    provider_cancellation_id: UUID
    provider_name: str
    feedback_type: str
    successfully_cancelled: Optional[bool]
    time_taken_minutes: Optional[int]
    helpfulness_rating: Optional[int]
    accuracy_rating: Optional[int]
    comment: Optional[str]
    issues_encountered: Optional[List[str]]
    ai_confidence_at_feedback: Optional[float]
    validation_quality_at_feedback: Optional[float]
    prompt_version_at_feedback: Optional[str]
    device_type: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProviderMetrics(BaseModel):
    """Metrics for a specific provider"""

    provider_name: str
    total_feedback: int
    helpful_count: int  # helpful or worked
    not_helpful_count: int  # not_helpful or failed
    success_rate: Optional[float]  # % of successfully_cancelled=True
    avg_time_minutes: Optional[float]  # Renamed from avg_time_taken_minutes
    avg_helpfulness: Optional[float]  # Renamed from avg_helpfulness_rating
    avg_accuracy: Optional[float]  # Renamed from avg_accuracy_rating
    common_issues: List[str] = Field(default_factory=list)  # List of common issues


class ValidationMetrics(BaseModel):
    """Overall feedback and validation metrics"""

    total_feedback: int
    high_confidence_success_rate: Optional[float]
    low_confidence_success_rate: Optional[float]
    providers_needing_update: List[str]  # List of provider names


class DashboardMetrics(BaseModel):
    """Complete dashboard metrics"""

    overall_metrics: ValidationMetrics  # Renamed from 'validation' to match frontend
    provider_metrics: List[ProviderMetrics]


class QuickFeedback(BaseModel):
    """Quick thumbs up/down feedback"""

    provider_cancellation_id: UUID
    was_helpful: bool  # True = thumbs up, False = thumbs down
    comment: Optional[str] = Field(None, max_length=500)
