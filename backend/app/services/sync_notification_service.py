"""In-app notification triggers for sync events.

Two thresholds:
- Circuit breaker tripped -> severity HIGH notification
- Sync ended with > SKIP_THRESHOLD skipped emails -> severity MEDIUM notification

Below threshold (1-10 skips) -> no notification, the mailbox card badge is
sufficient signal.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mailbox import Mailbox
from app.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)

logger = logging.getLogger(__name__)

SKIP_THRESHOLD = 10


def notify_sync_skipped_many(
    db: Session, mailbox: Mailbox, skipped_count: int
) -> Optional[Notification]:
    """Create an in-app notification when many emails were skipped."""
    if skipped_count <= SKIP_THRESHOLD:
        return None
    notif = Notification(
        user_id=mailbox.user_id,
        type=NotificationType.SYNC_SKIPPED_MANY,
        priority=NotificationPriority.MEDIUM,
        title="Sync completed with errors",
        message=(
            f"Your last sync of {mailbox.email_address} skipped {skipped_count} "
            f"emails. View details to retry or ignore them."
        ),
        notification_metadata={
            "mailbox_id": str(mailbox.id),
            "skipped_count": skipped_count,
            "deeplink": f"/mailboxes/{mailbox.id}/sync-errors",
        },
    )
    db.add(notif)
    db.commit()
    return notif


def notify_sync_circuit_breaker(
    db: Session, mailbox: Mailbox, error_count: int
) -> Notification:
    """Create a HIGH-priority notification when the circuit breaker tripped."""
    notif = Notification(
        user_id=mailbox.user_id,
        type=NotificationType.SYNC_CIRCUIT_BREAKER,
        priority=NotificationPriority.HIGH,
        title="Sync interrupted by safety circuit breaker",
        message=(
            f"Sync of {mailbox.email_address} was stopped after "
            f"{error_count} consecutive unexpected errors. "
            f"This usually indicates a system issue - please retry later "
            f"or contact support."
        ),
        notification_metadata={
            "mailbox_id": str(mailbox.id),
            "error_count": error_count,
            "deeplink": f"/mailboxes/{mailbox.id}/sync-errors",
        },
    )
    db.add(notif)
    db.commit()
    return notif
