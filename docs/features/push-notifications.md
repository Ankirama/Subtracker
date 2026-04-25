# Push Notifications Backend Implementation Guide

## Overview

This document outlines the backend implementation required to support Web Push Notifications for the Subscription Tracker PWA.

## Prerequisites

- Frontend PWA setup complete (service worker registered)
- Frontend PushNotificationSettings component integrated
- Python 3.9+ with FastAPI
- PostgreSQL database

## Implementation Steps

### 1. Install Required Dependencies

```bash
cd backend
pip install pywebpush cryptography
```

Update `requirements.txt`:
```
pywebpush==1.14.0
cryptography==41.0.0
```

### 2. Generate VAPID Keys

Create a script to generate VAPID keys (one-time setup):

```python
# scripts/generate_vapid_keys.py
from pywebpush import webpush, WebPushException
from py_vapid import Vapid

vapid = Vapid()
vapid.generate_keys()

print("VAPID Keys Generated:")
print(f"Public Key: {vapid.public_key.decode('utf-8')}")
print(f"Private Key: {vapid.private_key.decode('utf-8')}")
print("\nAdd these to your .env file:")
print(f"VAPID_PUBLIC_KEY={vapid.public_key.decode('utf-8')}")
print(f"VAPID_PRIVATE_KEY={vapid.private_key.decode('utf-8')}")
print(f"VAPID_CLAIM_EMAIL=mailto:your-email@example.com")
```

Run and save the keys:
```bash
python scripts/generate_vapid_keys.py
```

### 3. Update Environment Configuration

Add to `.env`:
```env
VAPID_PUBLIC_KEY=<generated_public_key>
VAPID_PRIVATE_KEY=<generated_private_key>
VAPID_CLAIM_EMAIL=mailto:your-email@example.com
```

### 4. Create Database Models

```python
# app/models/push_subscription.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import uuid

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="push_subscriptions")

    def to_dict(self):
        return {
            "id": self.id,
            "endpoint": self.endpoint,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }
```

Update User model:
```python
# Add to User model
push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")
```

### 5. Create Pydantic Schemas

```python
# app/schemas/push_notification.py
from pydantic import BaseModel
from typing import Dict

class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys

class PushSubscriptionResponse(BaseModel):
    id: str
    endpoint: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True

class PushNotificationPayload(BaseModel):
    title: str
    body: str
    icon: str = "/icon-192.svg"
    badge: str = "/icon-192.svg"
    tag: str = "subscription-tracker"
    data: Dict = {}
```

### 6. Create Push Notification Service

```python
# app/services/push_notification_service.py
from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session
from app.models.push_subscription import PushSubscription
from app.core.config import settings
import json
import logging

logger = logging.getLogger(__name__)

class PushNotificationService:
    def __init__(self):
        self.vapid_private_key = settings.VAPID_PRIVATE_KEY
        self.vapid_claims = {"sub": settings.VAPID_CLAIM_EMAIL}

    async def send_notification(
        self,
        subscription: PushSubscription,
        title: str,
        body: str,
        icon: str = "/icon-192.svg",
        data: dict = None
    ) -> bool:
        """Send a push notification to a subscription."""
        try:
            payload = json.dumps({
                "title": title,
                "body": body,
                "icon": icon,
                "badge": icon,
                "tag": "subscription-tracker",
                "data": data or {},
            })

            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                }
            }

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )

            logger.info(f"Push notification sent to subscription {subscription.id}")
            return True

        except WebPushException as ex:
            logger.error(f"Push notification failed: {ex}")
            if ex.response and ex.response.status_code == 410:
                # Subscription expired, mark as inactive
                logger.info(f"Marking subscription {subscription.id} as inactive")
                return False
            raise

    async def send_to_user(
        self,
        db: Session,
        user_id: str,
        title: str,
        body: str,
        icon: str = "/icon-192.svg",
        data: dict = None
    ):
        """Send push notification to all active subscriptions for a user."""
        subscriptions = db.query(PushSubscription).filter(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True
        ).all()

        success_count = 0
        for subscription in subscriptions:
            try:
                success = await self.send_notification(
                    subscription, title, body, icon, data
                )
                if success:
                    success_count += 1
                else:
                    # Mark subscription as inactive
                    subscription.is_active = False
                    db.commit()
            except Exception as e:
                logger.error(f"Error sending to subscription {subscription.id}: {e}")

        return success_count

push_notification_service = PushNotificationService()
```

### 7. Create API Endpoints

```python
# app/api/v1/endpoints/push_notifications.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.push_subscription import PushSubscription
from app.schemas.push_notification import (
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    PushNotificationPayload
)
from app.services.push_notification_service import push_notification_service
from app.core.config import settings

router = APIRouter()

@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Get VAPID public key for push subscription."""
    return {"publicKey": settings.VAPID_PUBLIC_KEY}

@router.post("/subscribe", response_model=PushSubscriptionResponse)
async def subscribe_to_push(
    subscription: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Subscribe to push notifications."""
    # Check if subscription already exists
    existing = db.query(PushSubscription).filter(
        PushSubscription.endpoint == subscription.endpoint
    ).first()

    if existing:
        # Update existing subscription
        existing.p256dh = subscription.keys.p256dh
        existing.auth = subscription.keys.auth
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing.to_dict()

    # Create new subscription
    new_subscription = PushSubscription(
        user_id=current_user.id,
        endpoint=subscription.endpoint,
        p256dh=subscription.keys.p256dh,
        auth=subscription.keys.auth
    )

    db.add(new_subscription)
    db.commit()
    db.refresh(new_subscription)

    return new_subscription.to_dict()

@router.delete("/unsubscribe")
async def unsubscribe_from_push(
    endpoint: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unsubscribe from push notifications."""
    subscription = db.query(PushSubscription).filter(
        PushSubscription.endpoint == endpoint,
        PushSubscription.user_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    db.delete(subscription)
    db.commit()

    return {"message": "Unsubscribed successfully"}

@router.get("/subscriptions", response_model=List[PushSubscriptionResponse])
async def get_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all push subscriptions for current user."""
    subscriptions = db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id
    ).all()

    return [sub.to_dict() for sub in subscriptions]

@router.post("/test")
async def send_test_notification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a test push notification."""
    count = await push_notification_service.send_to_user(
        db,
        current_user.id,
        "Test Notification",
        "This is a test push notification from Subscription Tracker",
        data={"type": "test"}
    )

    return {"message": f"Sent to {count} subscription(s)"}
```

Register the router:
```python
# app/api/v1/api.py
from app.api.v1.endpoints import push_notifications

api_router.include_router(
    push_notifications.router,
    prefix="/push",
    tags=["push-notifications"]
)
```

### 8. Integrate with Notification System

Update the notification tasks to send push notifications:

```python
# app/tasks/notification_tasks.py

# Add to renewal reminder task
@celery_app.task
def send_renewal_reminders():
    # ... existing code ...

    # Send push notification
    if user_pref.push_enabled:  # Add push_enabled field to preferences
        from app.services.push_notification_service import push_notification_service
        await push_notification_service.send_to_user(
            db,
            user_id,
            f"{subscription.provider} Renewal",
            f"Your subscription renews in {days} days for {subscription.amount} {subscription.currency}",
            data={
                "type": "renewal_reminder",
                "subscription_id": subscription.id,
                "url": f"/subscriptions/{subscription.id}"
            }
        )
```

### 9. Database Migration

Create migration:
```bash
alembic revision --autogenerate -m "Add push subscriptions table"
alembic upgrade head
```

### 10. Update Frontend to Use Backend Keys

Update `PushNotificationSettings.tsx`:

```typescript
// Fetch VAPID public key from backend
useEffect(() => {
  fetchVapidKey()
}, [])

const fetchVapidKey = async () => {
  try {
    const response = await fetch(`${API_URL}/api/v1/push/vapid-public-key`)
    const data = await response.json()
    setVapidPublicKey(data.publicKey)
  } catch (error) {
    console.error('Error fetching VAPID key:', error)
  }
}

// Update subscribe function to send to backend
const subscribeToPush = async () => {
  // ... existing code ...

  // Send subscription to backend
  const response = await fetch(`${API_URL}/api/v1/push/subscribe`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(subscriptionData),
  })

  if (!response.ok) {
    throw new Error('Failed to save subscription')
  }
}
```

## Testing

### 1. Test Subscription Flow
```bash
# Start backend
cd backend
uvicorn app.main:app --reload

# Test VAPID key endpoint
curl http://localhost:8000/api/v1/push/vapid-public-key

# Test subscription (requires auth token)
curl -X POST http://localhost:8000/api/v1/push/subscribe \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://fcm.googleapis.com/...",
    "keys": {
      "p256dh": "...",
      "auth": "..."
    }
  }'
```

### 2. Test Push Notification
```bash
# Send test notification
curl -X POST http://localhost:8000/api/v1/push/test \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Test on Real Device
1. Build production PWA: `npm run build`
2. Serve with HTTPS (required for push): `npx serve -s dist -l 443`
3. Open on mobile device
4. Enable push notifications in settings
5. Trigger a test notification

## Production Considerations

### Security
- Always use HTTPS (push notifications require secure context)
- Keep VAPID private key secure (environment variable, not in code)
- Validate subscription endpoints
- Rate limit push notification endpoints

### Performance
- Batch notifications when possible
- Use background tasks/queues (Celery) for sending
- Clean up expired subscriptions regularly
- Monitor delivery rates

### Monitoring
- Log all push notification attempts
- Track delivery failures
- Alert on high failure rates
- Monitor subscription churn

### Compliance
- Respect user preferences (easy unsubscribe)
- Don't spam with notifications
- Include privacy policy for data handling
- GDPR compliance for EU users

## Troubleshooting

### Common Issues

**Issue**: Push notifications not received
- Check browser support (Chrome, Firefox, Safari 16.4+)
- Verify HTTPS connection
- Check service worker is registered
- Verify VAPID keys match
- Check subscription is active in database

**Issue**: 410 Gone errors
- Subscription expired, clean up database
- User may have cleared browser data
- User may have unsubscribed at browser level

**Issue**: CORS errors
- Add frontend origin to CORS allowed origins
- Verify credentials are included in requests

## Resources

- [Web Push Protocol](https://datatracker.ietf.org/doc/html/rfc8030)
- [VAPID Specification](https://datatracker.ietf.org/doc/html/rfc8292)
- [Push API MDN](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [pywebpush Documentation](https://github.com/web-push-libs/pywebpush)
