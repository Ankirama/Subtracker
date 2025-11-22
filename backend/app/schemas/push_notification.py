from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime


class PushSubscriptionKeys(BaseModel):
    """Keys for push subscription."""

    p256dh: str = Field(..., description="Public key for encryption")
    auth: str = Field(..., description="Authentication secret")


class PushSubscriptionCreate(BaseModel):
    """Schema for creating a push subscription."""

    endpoint: str = Field(..., description="Push service endpoint URL")
    keys: PushSubscriptionKeys


class PushSubscriptionResponse(BaseModel):
    """Schema for push subscription response."""

    id: str
    endpoint: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PushNotificationPayload(BaseModel):
    """Schema for push notification payload."""

    title: str = Field(..., min_length=1, max_length=100, description="Notification title")
    body: str = Field(..., min_length=1, max_length=200, description="Notification body")
    icon: str = Field(default="/icon-192.svg", description="Icon URL")
    badge: str = Field(default="/icon-192.svg", description="Badge icon URL")
    tag: str = Field(default="subscription-tracker", description="Notification tag")
    data: Dict = Field(default_factory=dict, description="Additional data")
    url: Optional[str] = Field(default=None, description="URL to open on click")


class VAPIDPublicKeyResponse(BaseModel):
    """Schema for VAPID public key response."""

    publicKey: str = Field(..., description="VAPID public key in URL-safe base64 format")
