"""
Pydantic schemas for mailbox endpoints.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


class MailboxCreate(BaseModel):
    """Schema for creating a new mailbox connection."""

    provider_type: Literal["jmap", "gmail", "outlook"] = Field(
        ..., description="Email provider type"
    )
    email_address: EmailStr = Field(..., description="Email address for the mailbox")
    credentials: dict = Field(
        ..., description="Provider-specific credentials (will be encrypted)"
    )
    display_name: Optional[str] = Field(
        None, description="Custom display name for this mailbox"
    )
    sync_frequency: Literal["manual", "daily", "weekly"] = Field(
        default="weekly", description="How often to sync emails"
    )
    batch_size: int = Field(
        default=100, ge=10, le=1000, description="Number of emails to process per batch"
    )
    import_date_filter: Optional[str] = Field(
        None, description="Date filter for import (e.g., '1year', '2years', 'all')"
    )

    @field_validator("credentials")
    @classmethod
    def validate_credentials(cls, v: dict, info) -> dict:
        """Validate credentials based on provider type."""
        provider = info.data.get("provider_type")

        if provider == "jmap":
            # JMAP requires: server_url, username, password/token
            required = ["server_url", "username", "password"]
            if not all(k in v for k in required):
                raise ValueError(
                    f'JMAP credentials must include: {", ".join(required)}'
                )
        elif provider == "gmail":
            # Gmail requires OAuth tokens
            required = ["access_token", "refresh_token", "client_id", "client_secret"]
            if not all(k in v for k in required):
                raise ValueError(
                    f'Gmail credentials must include: {", ".join(required)}'
                )
        elif provider == "outlook":
            # Outlook requires OAuth tokens
            required = ["access_token", "refresh_token", "client_id", "client_secret"]
            if not all(k in v for k in required):
                raise ValueError(
                    f'Outlook credentials must include: {", ".join(required)}'
                )

        return v


class MailboxUpdate(BaseModel):
    """Schema for updating mailbox settings."""

    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    sync_frequency: Optional[Literal["manual", "daily", "weekly"]] = None
    batch_size: Optional[int] = Field(None, ge=10, le=1000)
    import_date_filter: Optional[str] = None
    credentials: Optional[dict] = None  # Allow updating credentials


class MailboxResponse(BaseModel):
    """Schema for mailbox response (without sensitive data)."""

    id: UUID
    user_id: UUID
    provider_type: str
    email_address: str
    display_name: Optional[str]
    is_active: bool
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_emails_processed: Optional[int] = None
    last_sync_subscriptions_found: Optional[int] = None
    last_sync_error_message: Optional[str] = None
    sync_frequency: str
    batch_size: int
    import_date_filter: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MailboxSyncRequest(BaseModel):
    """Schema for triggering mailbox synchronization."""

    force_full_sync: bool = Field(
        default=False, description="If true, ignore last sync and reimport all"
    )
    date_filter_override: Optional[str] = Field(
        None, description="Override default import_date_filter for this sync"
    )


class MailboxSyncStatus(BaseModel):
    """Schema for mailbox sync status response."""

    mailbox_id: UUID
    status: Literal["success", "failed", "in_progress", "queued", "never_synced"]
    last_sync_at: Optional[datetime]
    total_emails_processed: Optional[int] = None
    subscriptions_found: Optional[int] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MailboxTestConnection(BaseModel):
    """Schema for testing mailbox connection before saving."""

    provider_type: Literal["jmap", "gmail", "outlook"]
    credentials: dict


class MailboxTestResult(BaseModel):
    """Schema for connection test result."""

    success: bool
    message: str
    provider_info: Optional[dict] = (
        None  # Provider-specific info (e.g., account name, mailbox count)
    )
