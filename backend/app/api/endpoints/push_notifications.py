from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.security.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.push_subscription import PushSubscription
from app.schemas.push_notification import (
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    VAPIDPublicKeyResponse,
)
from app.services.push_notification_service import push_notification_service
from app.config import settings

router = APIRouter()


@router.get("/vapid-public-key", response_model=VAPIDPublicKeyResponse)
async def get_vapid_public_key():
    """
    Get VAPID public key for push subscription.

    Returns:
        VAPIDPublicKeyResponse: Public key in URL-safe base64 format
    """
    return {"publicKey": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", response_model=PushSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_to_push(
    subscription: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Subscribe to push notifications.

    Creates a new push subscription or updates an existing one.

    Args:
        subscription: Push subscription data
        db: Database session
        current_user: Currently authenticated user

    Returns:
        PushSubscriptionResponse: Created or updated subscription
    """
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
        user_id=str(current_user.id),
        endpoint=subscription.endpoint,
        p256dh=subscription.keys.p256dh,
        auth=subscription.keys.auth
    )

    db.add(new_subscription)
    db.commit()
    db.refresh(new_subscription)

    return new_subscription.to_dict()


@router.delete("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_from_push(
    endpoint: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unsubscribe from push notifications.

    Removes a push subscription by endpoint.

    Args:
        endpoint: Push subscription endpoint URL
        db: Database session
        current_user: Currently authenticated user

    Raises:
        HTTPException: 404 if subscription not found
    """
    subscription = db.query(PushSubscription).filter(
        PushSubscription.endpoint == endpoint,
        PushSubscription.user_id == str(current_user.id)
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    db.delete(subscription)
    db.commit()


@router.get("/subscriptions", response_model=List[PushSubscriptionResponse])
async def get_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all push subscriptions for current user.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List[PushSubscriptionResponse]: List of user's push subscriptions
    """
    subscriptions = db.query(PushSubscription).filter(
        PushSubscription.user_id == str(current_user.id)
    ).all()

    return [sub.to_dict() for sub in subscriptions]


@router.post("/test", status_code=status.HTTP_200_OK)
async def send_test_notification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a test push notification to all user's subscriptions.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        dict: Message with count of sent notifications
    """
    count = await push_notification_service.send_to_user(
        db,
        str(current_user.id),
        "Test Notification",
        "This is a test push notification from Subscription Tracker",
        data={"type": "test"}
    )

    return {"message": f"Sent to {count} subscription(s)"}
