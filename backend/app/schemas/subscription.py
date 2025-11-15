"""
Pydantic schemas for subscription endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class SubscriptionBase(BaseModel):
    """Base schema with common subscription fields."""
    provider: str = Field(..., min_length=1, max_length=255, description="Service provider name")
    amount: Optional[float] = Field(None, ge=0, description="Subscription amount")
    currency: Optional[str] = Field(None, max_length=3, description="Currency code (USD, EUR, etc.)")
    billing_cycle: Optional[Literal['monthly', 'yearly', 'weekly', 'one-time', 'none']] = None
    renewal_date: Optional[datetime] = None
    description: Optional[str] = Field(None, max_length=500)
    category: Literal['streaming', 'software', 'storage', 'productivity', 'entertainment', 'fitness', 'gaming', 'news', 'education', 'communication', 'finance', 'shopping', 'music', 'other'] = 'other'
    status: Literal['active', 'cancelled', 'paused', 'trial'] = 'active'


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a subscription manually."""
    mailbox_id: UUID
    
    @field_validator('currency')
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
    billing_cycle: Optional[Literal['monthly', 'yearly', 'weekly', 'one-time', 'none']] = None
    renewal_date: Optional[datetime] = None
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[Literal['streaming', 'software', 'storage', 'productivity', 'entertainment', 'fitness', 'gaming', 'news', 'education', 'communication', 'finance', 'shopping', 'music', 'other']] = None
    status: Optional[Literal['active', 'cancelled', 'paused', 'trial']] = None
    notes: Optional[str] = None
    
    @field_validator('currency')
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

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str,
            Decimal: float
        }


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

    class Config:
        from_attributes = True


class SubscriptionEmailLink(BaseModel):
    """Schema for subscription-email relationship."""
    email: EmailMessageResponse
    extraction_role: Optional[str] = None
    extraction_data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SubscriptionDetailResponse(SubscriptionResponse):
    """Extended subscription response with source emails and metadata."""
    source_emails: list[SubscriptionEmailLink] = []

    class Config:
        from_attributes = True
