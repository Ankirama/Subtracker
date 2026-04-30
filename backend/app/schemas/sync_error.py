"""Pydantic v2 schemas for sync error endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SyncErrorOut(BaseModel):
    """User-facing sync error (PII-safe — no raw_payload, no stack_trace)."""

    id: UUID
    mailbox_id: UUID
    sync_history_id: Optional[UUID] = None
    provider_message_id: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    error_type: str
    error_message: str
    severity: str
    status: str
    resolution: Optional[str] = None
    retry_count: int
    last_retry_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncErrorAdminOut(SyncErrorOut):
    """Admin view: includes raw_payload and stack_trace."""

    stack_trace: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None
    resolved_by_id: Optional[UUID] = None


class SyncErrorListOut(BaseModel):
    items: List[SyncErrorOut]
    total: int
    page: int
    page_size: int


class SyncErrorAdminListOut(BaseModel):
    items: List[SyncErrorAdminOut]
    total: int
    page: int
    page_size: int


class RetryResponseOut(BaseModel):
    task_id: str = Field(..., description="Celery task id for the retry batch")
    pending_count: int = Field(..., description="Number of errors queued for retry")
