"""Cancellation-suggestion creation step for the email-sync pipeline.

When the AI classifier tags an email as ``category="cancellation"`` and
the matched subscription has no pending suggestion yet, populate
``suggested_cancellation_status``, ``cancellation_suggestion_reason`` and
``cancellation_suggestion_created_at`` on the subscription.

If a *new* suggestion was created, the function returns a
:class:`CancellationSuggestionCreated` payload so the caller can emit a
user-facing notification *after* the per-email transaction commits.
Returning ``None`` means either nothing was created or a suggestion was
already pending (no notification should be emitted in either case).

Best-effort: exceptions are logged but do not abort the per-batch loop.
Does NOT commit; the caller controls transaction boundaries.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.models.email_message import EmailMessage
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


@dataclass
class CancellationSuggestionCreated:
    """Snapshot of the data needed to emit a user notification.

    Captured before the caller commits, then consumed after commit so the
    notification is only sent for suggestions that actually persisted.
    """

    subscription_id: UUID
    user_id: UUID
    provider: str
    reason: str


def maybe_create_cancellation_suggestion(
    subscription_record: Subscription, email_record: EmailMessage
) -> Optional[CancellationSuggestionCreated]:
    """Create a cancellation suggestion on the subscription if appropriate.

    Conditions for creation:
      - The email's classification reasoning carries ``category="cancellation"``.
      - The subscription does not already have a pending
        ``suggested_cancellation_status``.

    Returns the payload only when a NEW suggestion was created. Returns
    ``None`` if nothing was created (wrong category, suggestion already
    pending, or unexpected error).
    """
    try:
        classification = email_record.classification_reasoning or {}
        category = classification.get("category", "")

        if category != "cancellation":
            return None

        if subscription_record.suggested_cancellation_status:
            logger.info(
                f"Cancellation suggestion already exists for {subscription_record.provider}, skipping"
            )
            return None

        reason = classification.get(
            "reasoning",
            "AI detected a cancellation email",
        )
        subscription_record.suggested_cancellation_status = "cancelled"
        subscription_record.cancellation_suggestion_reason = reason
        subscription_record.cancellation_suggestion_created_at = datetime.now(
            timezone.utc
        )
        logger.info(
            f"Created cancellation suggestion for {subscription_record.provider}: {reason}"
        )
        return CancellationSuggestionCreated(
            subscription_id=subscription_record.id,
            user_id=subscription_record.user_id,
            provider=subscription_record.provider,
            reason=reason,
        )
    except Exception as e:  # noqa: BLE001 — best-effort, bad email mustn't abort batch
        logger.error(
            f"Error creating cancellation suggestion for {subscription_record.provider}: {str(e)}"
        )
        return None
