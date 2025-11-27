"""
Pydantic schemas for cancellation workflows
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from enum import Enum


# Enums matching database enums
class DifficultyRating(str, Enum):
    """Cancellation difficulty levels"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class InstructionsSource(str, Enum):
    """Source of cancellation instructions"""

    MANUAL = "manual"
    AI_GENERATED = "ai_generated"
    COMMUNITY = "community"
    VERIFIED = "verified"


class CancellationStatus(str, Enum):
    """Subscription cancellation status"""

    ACTIVE = "active"
    PENDING_CANCELLATION = "pending_cancellation"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# ProviderCancellationInfo schemas
class ProviderCancellationInfoBase(BaseModel):
    """Base schema for provider cancellation info"""

    provider_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Provider name (e.g., Netflix, Spotify)",
    )
    cancellation_url: Optional[str] = Field(
        None, description="Direct URL to cancellation page"
    )
    difficulty_rating: DifficultyRating = Field(
        default=DifficultyRating.MEDIUM, description="How difficult it is to cancel"
    )
    instructions: Optional[List[str]] = Field(
        None, description="Step-by-step cancellation instructions"
    )
    instructions_source: InstructionsSource = Field(
        default=InstructionsSource.AI_GENERATED, description="Source of instructions"
    )
    requires_phone_call: bool = Field(
        default=False, description="Does cancellation require a phone call?"
    )
    requires_chat: bool = Field(
        default=False, description="Does cancellation require live chat?"
    )
    allows_pause: bool = Field(
        default=False, description="Can subscription be paused instead of cancelled?"
    )
    pause_instructions: Optional[List[str]] = Field(
        None, description="Instructions for pausing subscription"
    )
    additional_notes: Optional[str] = Field(
        None, description="Important warnings or timing notes"
    )
    estimated_time_minutes: Optional[float] = Field(
        None, ge=0, description="Estimated time to complete cancellation"
    )
    cancellation_gotchas: Optional[List[str]] = Field(
        None, description="Common pitfalls or things to watch out for"
    )


class ProviderCancellationInfoCreate(ProviderCancellationInfoBase):
    """Schema for creating provider cancellation info"""

    pass


class ProviderCancellationInfoUpdate(BaseModel):
    """Schema for updating provider cancellation info"""

    cancellation_url: Optional[str] = None
    difficulty_rating: Optional[DifficultyRating] = None
    instructions: Optional[List[str]] = None
    instructions_source: Optional[InstructionsSource] = None
    requires_phone_call: Optional[bool] = None
    requires_chat: Optional[bool] = None
    allows_pause: Optional[bool] = None
    pause_instructions: Optional[List[str]] = None
    additional_notes: Optional[str] = None
    estimated_time_minutes: Optional[float] = None
    cancellation_gotchas: Optional[List[str]] = None


class ProviderCancellationInfoResponse(ProviderCancellationInfoBase):
    """Schema for provider cancellation info response"""

    id: UUID
    last_verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    ai_confidence_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="AI confidence (0.0-1.0)"
    )
    created_at: datetime
    updated_at: datetime

    # Computed properties
    is_verified: bool = Field(description="Whether instructions have been verified")
    needs_reverification: bool = Field(
        description="Whether instructions need reverification (>90 days old)"
    )
    is_ai_generated: bool = Field(description="Whether instructions were AI-generated")

    model_config = ConfigDict(from_attributes=True)


# AI Research schemas
class AIResearchRequest(BaseModel):
    """Request to research cancellation instructions with AI"""

    provider_name: str = Field(
        ..., min_length=1, max_length=255, description="Provider to research"
    )
    force_refresh: bool = Field(
        default=False, description="Force new research even if cached"
    )


class AIResearchResponse(BaseModel):
    """Response from AI cancellation research"""

    provider_name: str
    cancellation_url: Optional[str]
    difficulty_rating: DifficultyRating
    instructions: List[str]
    requires_phone_call: bool
    requires_chat: bool
    allows_pause: bool
    pause_instructions: Optional[List[str]]
    additional_notes: Optional[str]
    estimated_time_minutes: Optional[float]
    cancellation_gotchas: Optional[List[str]]
    ai_confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in accuracy (0.0-1.0)"
    )
    sources_consulted: Optional[List[str]] = Field(
        None, description="Sources AI consulted"
    )
    research_timestamp: datetime = Field(default_factory=datetime.utcnow)


# Subscription cancellation schemas
class SubscriptionCancellationStatusUpdate(BaseModel):
    """Update subscription cancellation status"""

    cancellation_status: CancellationStatus = Field(
        ..., description="New cancellation status"
    )
    cancellation_notes: Optional[str] = Field(
        None, description="Optional notes about cancellation"
    )


class SubscriptionCancellationInfo(BaseModel):
    """Cancellation info for a specific subscription"""

    subscription_id: UUID
    provider: str
    cancellation_status: CancellationStatus
    cancellation_requested_at: Optional[datetime]
    cancellation_confirmed_at: Optional[datetime]
    cancellation_notes: Optional[str]

    # Provider cancellation instructions (if available)
    provider_info: Optional[ProviderCancellationInfoResponse] = None


# Review suggestion schemas
class ReviewSuggestionReason(str, Enum):
    """Why a subscription is suggested for review"""

    TRIAL_ENDING = "trial_ending"
    TRIAL_ENDING_SOON = "trial_ending_soon"
    LIKELY_UNUSED = "likely_unused"
    PRICE_INCREASED = "price_increased"
    EXPENSIVE_UNUSED = "expensive_unused"
    DUPLICATE_DETECTED = "duplicate_detected"


class ReviewSuggestion(BaseModel):
    """Subscription suggested for review/cancellation"""

    subscription_id: UUID
    provider: str
    amount: Optional[float]
    currency: str
    billing_cycle: str

    # Suggestion details
    reason: ReviewSuggestionReason
    priority: str = Field(
        ..., description="Priority level: critical, high, medium, low"
    )
    message: str = Field(
        ..., description="User-friendly message explaining why to review"
    )
    action_by_date: Optional[datetime] = Field(
        None, description="When action should be taken (for trials)"
    )

    # Metadata
    days_since_last_email: Optional[int] = None
    price_change_amount: Optional[float] = None
    price_change_date: Optional[datetime] = None

    # Dismissal tracking
    dismissed_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None


class ReviewSuggestionsResponse(BaseModel):
    """Response with list of review suggestions"""

    suggestions: List[ReviewSuggestion]
    total_count: int
    critical_count: int = Field(
        description="Number of critical suggestions (trials ending today)"
    )
    high_priority_count: int = Field(description="Number of high priority suggestions")


class DismissReviewSuggestion(BaseModel):
    """Dismiss a review suggestion"""

    subscription_id: UUID
    permanent: bool = Field(default=True, description="Dismiss permanently or snooze?")
    snooze_days: Optional[int] = Field(
        None, ge=1, le=90, description="Days to snooze (if not permanent)"
    )


# List response schemas
class ProviderCancellationInfoListResponse(BaseModel):
    """Paginated list of provider cancellation info"""

    items: List[ProviderCancellationInfoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
