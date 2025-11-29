"""
Pydantic schemas for AI Sandbox API endpoints.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class EmailTestRequest(BaseModel):
    """Request schema for testing email classification/extraction."""

    subject: str = Field(..., description="Email subject line")
    sender: str = Field(..., description="Email sender address")
    sender_name: Optional[str] = Field(None, description="Sender display name")
    body_text: Optional[str] = Field(None, description="Plain text email body")
    body_html: Optional[str] = Field(None, description="HTML email body")
    date: Optional[datetime] = Field(None, description="Email date")


class ClassificationTestResponse(BaseModel):
    """Response schema for classification test."""

    is_subscription: bool
    confidence: float
    reasoning: str
    category: str


class ExtractionTestResponse(BaseModel):
    """Response schema for extraction test."""

    provider: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    billing_cycle: Optional[str]
    renewal_date: Optional[str]
    custom_label: Optional[str]
    category: str
    confidence_score: float
    extraction_method: str
    raw_response: Optional[Dict[str, Any]] = Field(
        None, description="Full AI response for debugging"
    )


class UncertainEmail(BaseModel):
    """Schema for uncertain email that needs review."""

    id: str
    subject: str
    sender: str
    sender_name: Optional[str]
    date: datetime
    classification_confidence: float
    is_subscription: bool
    has_linked_subscription: bool
    preview: str = Field(..., description="First 200 chars of email body")

    model_config = ConfigDict(from_attributes=True)


class UncertainEmailsResponse(BaseModel):
    """Response schema for listing uncertain emails."""

    emails: List[UncertainEmail]
    total: int
    uncertain_classified: int = Field(
        ...,
        description="Count of emails with is_subscription=true but confidence < 0.8",
    )
    extraction_failed: int = Field(
        ..., description="Count of emails classified but no subscription created"
    )


class EmailDetailResponse(BaseModel):
    """Detailed email information for review."""

    id: str
    subject: str
    sender: str
    sender_name: Optional[str]
    recipient: str
    date: datetime
    body_text: Optional[str]
    body_html: Optional[str]
    is_subscription: bool
    classification_confidence: float
    classification_reasoning: Optional[Dict[str, Any]]
    has_linked_subscription: bool
    linked_subscription_id: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ManualSubscriptionCreate(BaseModel):
    """Schema for manually creating a subscription from an email."""

    email_id: str
    provider: str
    amount: Optional[float]
    currency: Optional[str]
    billing_cycle: Optional[str]
    renewal_date: Optional[datetime]
    custom_label: Optional[str]
    category: str = "other"
    notes: Optional[str]


class BulkMarkNotSubscriptionRequest(BaseModel):
    """Schema for bulk marking emails as not subscriptions."""

    email_ids: List[str] = Field(
        ..., description="List of email IDs to mark as not subscriptions"
    )


class BulkMarkNotSubscriptionResponse(BaseModel):
    """Response schema for bulk mark not subscription operation."""

    success: bool
    processed: int = Field(..., description="Number of emails successfully processed")
    failed: int = Field(..., description="Number of emails that failed")
    errors: List[str] = Field(
        default_factory=list, description="Error messages for failed operations"
    )
