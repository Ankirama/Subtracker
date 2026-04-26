"""Cancellation-suggestion creation step for the email-sync pipeline.

When the AI classifier tags an email as ``category="cancellation"`` and
the matched subscription has no pending suggestion yet, populate
``suggested_cancellation_status``, ``cancellation_suggestion_reason`` and
``cancellation_suggestion_created_at`` on the subscription. Best-effort:
exceptions are logged but do not abort the per-batch loop.

Mirrors the inline block previously at ``_sync_mailbox_async`` lines
629-663 (pre-Phase-8b numbering). Does NOT commit; the caller controls
transaction boundaries.
"""

import logging
from datetime import datetime, timezone

from app.models.email_message import EmailMessage
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


def maybe_create_cancellation_suggestion(
    subscription_record: Subscription, email_record: EmailMessage
) -> None:
    """Create a cancellation suggestion on the subscription if appropriate.

    Conditions:
      - The email's classification reasoning carries ``category="cancellation"``.
      - The subscription does not already have a pending
        ``suggested_cancellation_status``.

    Best-effort: any unexpected ``Exception`` is logged and swallowed so
    a single bad email does not abort the batch.
    """
    try:
        classification = email_record.classification_reasoning or {}
        category = classification.get("category", "")

        if category == "cancellation":
            # Only create suggestion if no existing suggestion is pending
            if not subscription_record.suggested_cancellation_status:
                subscription_record.suggested_cancellation_status = "cancelled"
                subscription_record.cancellation_suggestion_reason = classification.get(
                    "reasoning",
                    "AI detected a cancellation email",
                )
                subscription_record.cancellation_suggestion_created_at = datetime.now(
                    timezone.utc
                )
                logger.info(
                    f"Created cancellation suggestion for {subscription_record.provider}: {classification.get('reasoning', 'No reason')}"
                )
            else:
                logger.info(
                    f"Cancellation suggestion already exists for {subscription_record.provider}, skipping"
                )
    except Exception as e:
        logger.error(
            f"Error creating cancellation suggestion for {subscription_record.provider}: {str(e)}"
        )
        # Continue even if suggestion creation fails
