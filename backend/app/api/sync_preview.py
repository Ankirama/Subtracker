"""GET /api/sync-history/{id}/preview - read-only preview of one sync run."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.email_message import EmailMessage, subscription_emails
from app.models.mailbox import Mailbox
from app.models.price_history import PriceHistory
from app.models.subscription import Subscription
from app.models.sync_history import SyncHistory
from app.models.user import User
from app.schemas.sync_preview import (
    NewSubscriptionPreview,
    SyncPreviewMeta,
    SyncPreviewResponse,
    UpdatedSubscriptionPreview,
)
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/api/sync-history", tags=["sync-preview"])

CONFIDENCE_AUTO_SAVED_THRESHOLD = Decimal("85.0")


def _bucket_for_confidence(score: Optional[Decimal]) -> str:
    """Map a numeric confidence score to its display bucket."""
    if score is not None and score >= CONFIDENCE_AUTO_SAVED_THRESHOLD:
        return "auto_saved"
    return "pending_review"


def _source_email_for_subscription(
    db: Session, subscription_id: UUID, role: str
) -> Optional[EmailMessage]:
    """Return the most recent linked email for a subscription with a given
    extraction_role, or None if no such link exists."""
    return (
        db.query(EmailMessage)
        .join(
            subscription_emails,
            subscription_emails.c.email_id == EmailMessage.id,
        )
        .filter(
            subscription_emails.c.subscription_id == subscription_id,
            subscription_emails.c.extraction_role == role,
        )
        .order_by(EmailMessage.date.desc())
        .first()
    )


@router.get("/{sync_history_id}/preview", response_model=SyncPreviewResponse)
def get_sync_preview(
    sync_history_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncPreviewResponse:
    """Return a read-only preview of subscriptions discovered or updated by a
    single sync run.

    Returns 404 if the sync history does not exist or belongs to another user.
    """
    sh = (
        db.query(SyncHistory)
        .join(Mailbox, Mailbox.id == SyncHistory.mailbox_id)
        .filter(
            SyncHistory.id == sync_history_id,
            Mailbox.user_id == current_user.id,
        )
        .options(joinedload(SyncHistory.mailbox))
        .first()
    )
    if not sh:
        raise HTTPException(status_code=404, detail="Sync history not found")

    new_rows = (
        db.query(Subscription)
        .filter(Subscription.discovered_via_sync_history_id == sync_history_id)
        .all()
    )
    new_subscriptions = []
    for sub in new_rows:
        src = _source_email_for_subscription(db, sub.id, "initial_detection")
        new_subscriptions.append(
            NewSubscriptionPreview(
                id=sub.id,
                provider=sub.provider,
                custom_label=sub.custom_label,
                amount=sub.amount,
                currency=sub.currency,
                billing_cycle=sub.billing_cycle,
                category=sub.category,
                confidence_bucket=_bucket_for_confidence(sub.confidence_score),
                source_email_subject=src.subject if src else None,
                source_email_date=src.date if src else None,
            )
        )

    price_rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.sync_history_id == sync_history_id)
        .all()
    )
    updated_subscriptions = []
    for ph in price_rows:
        sub = (
            db.query(Subscription).filter(Subscription.id == ph.subscription_id).first()
        )
        if sub is None:
            continue
        src = _source_email_for_subscription(db, sub.id, "price_update")
        updated_subscriptions.append(
            UpdatedSubscriptionPreview(
                id=sub.id,
                provider=sub.provider,
                update_type="price_change",
                before={
                    "amount": (
                        float(ph.old_amount) if ph.old_amount is not None else None
                    )
                },
                after={"amount": float(ph.new_amount)},
                source_email_subject=src.subject if src else None,
                source_email_date=src.date if src else None,
            )
        )

    return SyncPreviewResponse(
        sync_history=SyncPreviewMeta(
            id=sh.id,
            mailbox_id=sh.mailbox_id,
            mailbox_email=sh.mailbox.email_address,
            started_at=sh.started_at,
            completed_at=sh.completed_at,
            new_emails_count=sh.new_emails_count,
        ),
        new_subscriptions=new_subscriptions,
        updated_subscriptions=updated_subscriptions,
    )
