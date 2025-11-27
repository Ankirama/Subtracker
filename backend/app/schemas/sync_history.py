"""
Pydantic schemas for sync history endpoints.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class SyncHistoryBase(BaseModel):
    """Base schema for sync history."""

    mailbox_id: UUID
    started_at: datetime
    status: str
    total_emails_processed: int = 0
    subscriptions_found: int = 0
    subscriptions_updated: int = 0
    batches_processed: int = 0


class SyncHistoryResponse(SyncHistoryBase):
    """Schema for sync history response."""

    id: UUID
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    sync_type: Optional[str] = None
    date_filter_used: Optional[str] = None
    batch_size_used: Optional[int] = None
    was_resumed: bool = False
    resumed_from_position: Optional[int] = None
    resumed_from_batch: Optional[int] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    final_position: Optional[int] = None
    final_batch_number: Optional[int] = None
    final_progress_percentage: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncHistoryList(BaseModel):
    """Schema for paginated sync history list."""

    items: list[SyncHistoryResponse]
    total: int
    limit: int
    offset: int


class SyncStatistics(BaseModel):
    """Schema for sync statistics summary."""

    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    cancelled_syncs: int
    total_emails_processed: int
    total_subscriptions_found: int
    average_duration_seconds: Optional[float] = None
    last_successful_sync: Optional[datetime] = None
    last_failed_sync: Optional[datetime] = None


class SyncProgressResponse(BaseModel):
    """Schema for real-time sync progress (Issue #10)."""

    mailbox_id: UUID
    status: str  # 'in_progress', 'queued', 'completed', 'failed', 'cancelled'
    current_batch_number: Optional[int] = None
    total_batches_estimate: Optional[int] = None
    progress_percentage: Optional[float] = None
    estimated_completion_time: Optional[datetime] = None
    emails_processed: Optional[int] = None
    subscriptions_found: Optional[int] = None
    started_at: Optional[datetime] = None
    elapsed_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
