"""
Pydantic schemas for subscription endpoints.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Literal
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class SubscriptionBase(BaseModel):
    """Base schema with common subscription fields."""

    provider: str = Field(
        ..., min_length=1, max_length=255, description="Service provider name"
    )
    amount: Optional[float] = Field(None, ge=0, description="Subscription amount")
    currency: Optional[str] = Field(
        None, max_length=3, description="Currency code (USD, EUR, etc.)"
    )
    billing_cycle: Optional[
        Literal[
            "monthly", "yearly", "weekly", "quarterly", "biannual", "one-time", "none"
        ]
    ] = None
    renewal_date: Optional[datetime] = None
    notes: Optional[str] = Field(
        None, max_length=500, description="Optional notes about the subscription"
    )
    category: str = Field(
        default="other",
        max_length=100,
        description="Subscription category (default or custom)",
    )
    custom_label: Optional[str] = Field(
        None,
        max_length=255,
        description="Custom label to differentiate multiple accounts",
    )
    is_active: bool = Field(
        default=True, description="Whether the subscription is currently active"
    )


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a subscription manually."""

    mailbox_id: UUID

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.upper()
        return v


class SubscriptionUpdate(BaseModel):
    """Schema for updating subscription."""

    provider: Optional[str] = Field(None, min_length=1, max_length=255)
    amount: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    billing_cycle: Optional[
        Literal[
            "monthly", "yearly", "weekly", "quarterly", "biannual", "one-time", "none"
        ]
    ] = None
    renewal_date: Optional[datetime] = None
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[
        Literal[
            "streaming",
            "software",
            "storage",
            "productivity",
            "entertainment",
            "fitness",
            "gaming",
            "news",
            "education",
            "communication",
            "finance",
            "shopping",
            "music",
            "other",
        ]
    ] = None
    custom_label: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    manual_status_override: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.upper()
        return v


class SubscriptionResponse(SubscriptionBase):
    """Schema for subscription response."""

    id: UUID
    mailbox_id: UUID
    confidence_score: float
    extraction_method: str
    payment_method_last4: Optional[str] = None
    notes: Optional[str] = None
    first_detected_at: datetime
    last_confirmed_at: datetime
    created_at: datetime
    updated_at: datetime
    next_renewal_date: Optional[datetime] = Field(
        None, description="Computed next future renewal date"
    )

    model_config = ConfigDict(from_attributes=True)


class SubscriptionListResponse(BaseModel):
    """Schema for paginated subscription list."""

    subscriptions: list[SubscriptionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class CategoryStats(BaseModel):
    """Stats for a subscription category."""

    count: int
    total: float


class SubscriptionStats(BaseModel):
    """Schema for subscription statistics."""

    total_subscriptions: int
    active_subscriptions: int
    total_monthly_cost: float
    total_yearly_cost: float
    by_category: dict[str, CategoryStats]
    by_billing_cycle: dict[str, int]
    upcoming_renewals: list[SubscriptionResponse]


class EmailMessageResponse(BaseModel):
    """Schema for email message response."""

    id: UUID
    mailbox_id: UUID
    message_id: str
    subject: str
    sender: str
    sender_name: Optional[str] = None
    recipient: str
    date: datetime
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    is_subscription: bool
    classification_confidence: Optional[float] = None
    classification_reasoning: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionEmailLink(BaseModel):
    """Schema for subscription-email relationship."""

    email: EmailMessageResponse
    extraction_role: Optional[str] = None
    extraction_data: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionDetailResponse(SubscriptionResponse):
    """Extended subscription response with source emails and metadata."""

    source_emails: list[SubscriptionEmailLink] = []

    model_config = ConfigDict(from_attributes=True)


class MonthlySpendingData(BaseModel):
    """Monthly spending analytics data point."""

    month: str  # Format: "2024-01" or "Jan 2024"
    year: int
    month_num: int
    total_cost: float
    subscription_count: int
    new_subscriptions: int
    cancelled_subscriptions: int


class CategorySpendingTrend(BaseModel):
    """Category spending over time."""

    category: str
    monthly_data: list[dict]  # {month, amount}


class AnalyticsResponse(BaseModel):
    """Analytics data response."""

    monthly_spending: list[MonthlySpendingData]
    category_trends: list[CategorySpendingTrend]
    total_spent: float
    average_monthly_cost: float
    peak_month: Optional[str] = None
    peak_month_cost: Optional[float] = None


class FeedbackCreate(BaseModel):
    """Schema for creating subscription feedback."""

    subscription_id: UUID
    feedback_type: Literal[
        "not_subscription",
        "duplicate",
        "wrong_amount",
        "wrong_provider",
        "wrong_category",
        "wrong_billing_cycle",
        "other",
    ]
    feedback_text: Optional[str] = Field(
        None, max_length=1000, description="Optional explanation"
    )


class FeedbackResponse(BaseModel):
    """Schema for feedback response."""

    id: UUID
    user_id: UUID
    subscription_id: UUID
    feedback_type: str
    feedback_text: Optional[str] = None
    subscription_snapshot: dict
    ai_classification_data: Optional[dict] = None
    source_email_ids: list[UUID] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
