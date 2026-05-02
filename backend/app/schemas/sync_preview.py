"""Pydantic schemas for the post-sync subscription preview."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncPreviewMeta(BaseModel):
    id: UUID
    mailbox_id: UUID
    mailbox_email: str
    started_at: datetime
    completed_at: Optional[datetime]
    new_emails_count: Optional[int]


class NewSubscriptionPreview(BaseModel):
    id: UUID
    provider: str
    custom_label: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str
    billing_cycle: str
    category: Optional[str] = None
    confidence_bucket: Literal["auto_saved", "pending_review"]
    source_email_subject: Optional[str] = None
    source_email_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UpdatedSubscriptionPreview(BaseModel):
    id: UUID
    provider: str
    update_type: Literal["price_change", "cancellation_detected"]
    before: dict[str, Any]
    after: dict[str, Any]
    source_email_subject: Optional[str] = None
    source_email_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SyncPreviewResponse(BaseModel):
    sync_history: SyncPreviewMeta
    new_subscriptions: list[NewSubscriptionPreview]
    updated_subscriptions: list[UpdatedSubscriptionPreview]
