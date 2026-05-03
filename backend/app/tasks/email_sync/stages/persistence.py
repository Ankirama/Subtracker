"""STAGE 3 — Persistence stage of the email-sync pipeline.

For every (email, extraction) pair produced by stage 2, decide whether
the candidate is a price update on an existing subscription, an upsert
on a matched existing subscription, or a brand-new subscription. Then:

  - record initial / change price history via ``..price_history``,
  - calculate renewal info via ``..renewal_step``,
  - create cancellation suggestions via ``..cancellation_step``,
  - insert the ``subscription_emails`` association row.

CRITICAL — commit boundary preservation
----------------------------------------
The per-email ``try/except`` arm wraps EVERY mutation for a single
email and ends with exactly one ``db.commit()`` on success and one
``db.rollback()`` on failure (continuing to the next email). This
matches the verbatim behaviour at pre-Phase-8b lines 372-704: Phase 1
chartests ``test_per_email_commit_increments_counter`` and
``commit_rollback_counter`` fixtures assert these counts. DO NOT batch
commits, hoist them out of the loop, or move them across the
``try``/``except`` boundary.

Returns updated counters ``(subscriptions_found, subscriptions_updated)``
which the orchestrator accumulates across batches.

The dedup decision is delegated to
``app.services.dedup_strategy.find_best_match`` (Phase 2 wiring). The
``ref_extractor_factory`` is injected by the orchestrator so tests can
drive dedup with a mock matcher (Phase 8a interface seam).
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.email_message import subscription_emails
from app.models.mailbox import Mailbox
from app.models.notification import NotificationPriority, NotificationType
from app.models.subscription import Subscription
from app.services.dedup_strategy import find_best_match
from app.services.email_pipeline_protocol import ReferenceExtractorFactory
from app.services.notification_service import NotificationService

from ..cancellation_step import (
    CancellationSuggestionCreated,
    maybe_create_cancellation_suggestion,
)
from ..filters import filter_subscription_data
from ..price_history import record_initial_price, record_price_change
from ..renewal_step import calculate_renewal_for_subscription

logger = logging.getLogger(__name__)


def persist_subscriptions_for_batch(
    db: Session,
    mailbox: Mailbox,
    subscription_email_records: List[tuple],
    subscription_data_list: List,
    *,
    subscriptions_found: int,
    subscriptions_updated: int,
    ref_extractor_factory: ReferenceExtractorFactory,
    sync_history_id: Optional[UUID] = None,
) -> Tuple[int, int]:
    """Stage 3: per-email upsert + history + renewal + cancellation + link.

    Args:
        db: SQLAlchemy session. The function commits / rolls back per
            email — see the module docstring for the boundary contract.
        mailbox: The mailbox being synced.
        subscription_email_records: ``[(provider_email, EmailMessage_row), ...]``
            from stage 2.
        subscription_data_list: extraction dicts (or ``None``) aligned
            with ``subscription_email_records``.
        subscriptions_found: running counter from prior batches.
        subscriptions_updated: running counter from prior batches.
        ref_extractor_factory: Injected factory returning a
            ``ReferenceExtractorProtocol`` instance, used to drive
            ``find_best_match``.
        sync_history_id: Optional FK to ``sync_history.id`` identifying
            the sync run that produced these rows. When provided, freshly
            inserted ``Subscription`` rows are tagged via
            ``discovered_via_sync_history_id`` and any
            ``PriceHistory`` rows recorded here carry the same
            ``sync_history_id``. ``None`` for non-sync callers (e.g.
            manual subscription creation), which keeps the FK NULL.

    Returns:
        ``(subscriptions_found, subscriptions_updated)`` after this batch.
    """
    for (email, email_record), subscription_data in zip(
        subscription_email_records, subscription_data_list
    ):
        try:
            if subscription_data:
                logger.info(f"Processing subscription data for: {email.subject}")

                # PRIORITY: Handle price updates detected by AI
                is_price_update = subscription_data.get("is_price_update", False)

                if is_price_update:
                    logger.info(f"Price update detected by AI for: {email.subject}")
                    old_amount = subscription_data.get("old_amount")
                    new_amount = subscription_data.get("new_amount")

                    # Search for existing subscription more aggressively for price updates
                    existing_sub = (
                        db.query(Subscription)
                        .filter(
                            Subscription.mailbox_id == mailbox.id,
                            Subscription.provider == subscription_data["provider"],
                        )
                        .first()
                    )

                    if existing_sub:
                        logger.info(
                            f"Found existing subscription for price update: {existing_sub.provider}"
                        )

                        # Update subscription with new price
                        existing_sub.amount = new_amount
                        existing_sub.updated_at = datetime.now(timezone.utc)

                        # Create price history record
                        record_price_change(
                            db,
                            existing_sub,
                            old_amount=old_amount,
                            new_amount=new_amount,
                            currency=subscription_data.get("currency")
                            or existing_sub.currency,
                            detected_from="email",
                            notes=f"Price update detected by AI from email: {email.subject}",
                            sync_history_id=sync_history_id,
                        )

                        # Link email to existing subscription
                        relationship_exists = db.execute(
                            subscription_emails.select().where(
                                subscription_emails.c.subscription_id
                                == existing_sub.id,
                                subscription_emails.c.email_id == email_record.id,
                            )
                        ).first()

                        if not relationship_exists:
                            extraction_data_json = {}
                            for key, value in subscription_data.items():
                                if isinstance(value, datetime):
                                    extraction_data_json[key] = value.isoformat()
                                else:
                                    extraction_data_json[key] = value

                            db.execute(
                                subscription_emails.insert().values(
                                    subscription_id=existing_sub.id,
                                    email_id=email_record.id,
                                    extraction_role="price_update",
                                    extraction_data=extraction_data_json,
                                )
                            )
                            logger.info("Linked price update email to subscription")

                        subscriptions_updated += 1
                        db.commit()
                        continue  # Skip normal processing, price update handled
                    else:
                        logger.warning(
                            "Price update detected but no existing subscription "
                            f"found for {subscription_data['provider']}, creating "
                            "new subscription"
                        )
                        # Fall through to normal creation logic

                # NORMAL PROCESSING: Check if subscription already exists
                # Strategy: Match LOOSELY on provider first, then use other fields for disambiguation
                # This prevents duplicates from:
                # - Different email_senders (e.g., PayPal vs direct provider email)
                # - Different billing_cycle values in emails
                # - AI-generated description variations

                # Primary match: Just provider + mailbox (most forgiving)
                base_query = db.query(Subscription).filter(
                    Subscription.mailbox_id == mailbox.id,
                    Subscription.provider == subscription_data["provider"],
                )

                # Get all potential matches for this provider
                potential_matches = base_query.all()

                # NORMAL PROCESSING: Check if subscription already exists
                # See app/services/dedup_strategy.py for the strategy ordering.
                # Strategies: service-ref → single-match → payment-processor →
                # email-sender → meaningful custom-label → fallback.
                # The factory is injected via `ref_extractor_factory` so
                # tests can drive dedup with a mock matcher; the seam
                # closes the lazy-import workaround tracked under audit
                # finding A.1.
                existing_sub = find_best_match(
                    subscription_data,
                    potential_matches,
                    ref_extractor=ref_extractor_factory(),
                )

                subscription_record = None
                if existing_sub:
                    # Check if price has changed before updating
                    old_amount = existing_sub.amount
                    new_amount = subscription_data.get("amount")
                    price_changed = (
                        old_amount is not None
                        and new_amount is not None
                        and float(old_amount) != float(new_amount)
                    )

                    # Update existing subscription (filter out metadata fields like is_price_update)
                    # Skip None values to avoid overwriting valid data with None and violating NOT NULL constraints
                    filtered_data = filter_subscription_data(subscription_data)
                    for key, value in filtered_data.items():
                        if value is not None:  # Only update with non-None values
                            setattr(existing_sub, key, value)
                    existing_sub.updated_at = datetime.now(timezone.utc)
                    subscription_record = existing_sub
                    subscriptions_updated += 1

                    # Create price history record if price changed
                    if price_changed:
                        record_price_change(
                            db,
                            existing_sub,
                            old_amount=old_amount,
                            new_amount=new_amount,
                            currency=subscription_data.get("currency", "EUR"),
                            detected_from="email",
                            notes=f"Price change detected from email: {email.subject}",
                            sync_history_id=sync_history_id,
                        )
                    else:
                        logger.info(
                            "Updated subscription: "
                            f"{subscription_data['provider']} - "
                            f"{subscription_data.get('custom_label') or 'No label'}"
                        )
                else:
                    # Create new subscription (filter out metadata fields like is_price_update)
                    filtered_data = filter_subscription_data(subscription_data)
                    new_subscription = Subscription(
                        user_id=mailbox.user_id,
                        mailbox_id=mailbox.id,
                        discovered_via_sync_history_id=sync_history_id,
                        **filtered_data,
                    )
                    db.add(new_subscription)
                    db.flush()  # Get the ID
                    subscription_record = new_subscription
                    subscriptions_found += 1
                    logger.info(
                        "Created new subscription: "
                        f"{subscription_data['provider']} - "
                        f"{subscription_data.get('custom_label') or 'No label'}"
                    )

                    # Create initial price history record
                    record_initial_price(
                        db,
                        new_subscription,
                        amount=subscription_data.get("amount"),
                        currency=subscription_data.get("currency", "EUR"),
                        detected_from="email",
                        notes=f"Initial price detected from email: {email.subject}",
                        sync_history_id=sync_history_id,
                    )

                # Calculate accurate renewal date and active status
                if subscription_record:
                    calculate_renewal_for_subscription(db, subscription_record)

                # Check for cancellation category and create suggestion.
                # Notification is emitted *after* the per-email commit
                # below so we never notify for a suggestion that didn't
                # persist.
                pending_cancellation_notification: Optional[
                    CancellationSuggestionCreated
                ] = None
                if subscription_record and email_record:
                    pending_cancellation_notification = (
                        maybe_create_cancellation_suggestion(
                            subscription_record, email_record
                        )
                    )

                # Create subscription-email relationship if not exists
                if subscription_record and email_record:
                    # Check if relationship already exists
                    relationship_exists = db.execute(
                        subscription_emails.select().where(
                            subscription_emails.c.subscription_id
                            == subscription_record.id,
                            subscription_emails.c.email_id == email_record.id,
                        )
                    ).first()

                    if not relationship_exists:
                        # Convert datetime objects to ISO strings for JSONB storage
                        extraction_data_json = {}
                        for key, value in subscription_data.items():
                            if isinstance(value, datetime):
                                extraction_data_json[key] = value.isoformat()
                            else:
                                extraction_data_json[key] = value

                        db.execute(
                            subscription_emails.insert().values(
                                subscription_id=subscription_record.id,
                                email_id=email_record.id,
                                extraction_role=(
                                    "detection" if not existing_sub else "update"
                                ),
                                extraction_data=extraction_data_json,
                            )
                        )
                        logger.info("Linked email to subscription")

            db.commit()

            # Emit cancellation notification post-commit. Best-effort: a
            # failed notification must not undo the persisted suggestion.
            if pending_cancellation_notification is not None:
                _emit_cancellation_notification(db, pending_cancellation_notification)

        except Exception as e:
            logger.error(f"Error processing email {email.id}: {str(e)}")
            db.rollback()
            continue

    return subscriptions_found, subscriptions_updated


def _emit_cancellation_notification(
    db: Session, payload: CancellationSuggestionCreated
) -> None:
    """Send the user a notification about a freshly-detected cancellation.

    Single-shot: ``maybe_create_cancellation_suggestion`` only returns a
    payload when a *new* suggestion is created (i.e. the subscription
    didn't already have a pending one), so no per-user/per-sub dedup is
    needed here.
    """
    try:
        NotificationService.create_notification(
            db=db,
            user_id=payload.user_id,
            notification_type=NotificationType.CANCELLATION_DETECTED,
            title=f"Possible cancellation detected: {payload.provider}",
            message=payload.reason,
            priority=NotificationPriority.MEDIUM,
            related_subscription_id=payload.subscription_id,
        )
    except Exception as e:  # noqa: BLE001 — notification is best-effort
        logger.error(
            f"Failed to emit cancellation notification for {payload.provider}: {e}"
        )
