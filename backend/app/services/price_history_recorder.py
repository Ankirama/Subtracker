"""
Helper functions for recording subscription price-change history.

These functions encapsulate the three PriceHistory creation paths that were
previously inlined (three times) inside tasks/email_sync._sync_mailbox_async:

  Path 1 (AI-flagged price update):  record_price_change(...)
  Path 2 (post-hoc amount diff):     record_price_change(...)  -- same helper
  Path 3 (new subscription initial): record_initial_price(...)

Both helpers add the new ORM instance to ``db`` but do NOT commit — the
caller controls transaction boundaries (this is required to preserve the
commit-counter behaviour that the Phase 1 chartests verify).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.price_history import PriceHistory
from app.models.subscription import Subscription

import logging

logger = logging.getLogger(__name__)


def record_price_change(
    db: Session,
    subscription: Subscription,
    old_amount,
    new_amount,
    *,
    currency: Optional[str] = None,
    detected_from: str = "email",
    notes: str = "",
    sync_history_id: Optional[UUID] = None,
) -> Optional[PriceHistory]:
    """
    Record an increase or decrease in a subscription's price.

    Both *old_amount* and *new_amount* must be non-None for a record to be
    created; if either is None, the function returns None without adding
    anything to the session.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.  The new ``PriceHistory`` row is added
        with ``db.add()`` but the session is NOT committed.
    subscription:
        The subscription whose price changed.
    old_amount:
        Previous price (Decimal, float, or int).
    new_amount:
        New price (Decimal, float, or int).
    currency:
        ISO-4217 currency code.  If omitted, falls back to
        ``subscription.currency`` (or ``"EUR"`` if that is also falsy).
    detected_from:
        Source of detection, e.g. ``"email"`` or ``"manual"``.
    notes:
        Free-text notes stored on the record.
    sync_history_id:
        Optional FK to ``sync_history.id`` identifying the sync run that
        produced this price change. ``None`` for non-sync paths (e.g.
        manual updates).

    Returns
    -------
    PriceHistory | None
        The newly created (but not yet committed) record, or ``None`` if
        either amount was None.
    """
    if old_amount is None or new_amount is None:
        return None

    old_f = float(old_amount)
    new_f = float(new_amount)

    change_percentage = ((new_f - old_f) / old_f) * 100
    change_type = "increase" if new_f > old_f else "decrease"

    resolved_currency = currency or getattr(subscription, "currency", "EUR") or "EUR"

    record = PriceHistory(
        subscription_id=subscription.id,
        old_amount=old_amount,
        new_amount=new_amount,
        currency=resolved_currency,
        change_type=change_type,
        change_percentage=round(change_percentage, 2),
        detected_from=detected_from,
        notes=notes,
        sync_history_id=sync_history_id,
    )
    db.add(record)
    logger.info(
        f"Price {change_type} for {subscription.provider}: "
        f"{old_amount} -> {new_amount} ({abs(change_percentage):.1f}%)"
    )
    return record


def record_initial_price(
    db: Session,
    subscription: Subscription,
    amount,
    *,
    currency: str = "EUR",
    detected_from: str = "email",
    notes: str = "",
    sync_history_id: Optional[UUID] = None,
) -> Optional[PriceHistory]:
    """
    Record the initial price for a newly created subscription.

    If *amount* is None, no record is created and the function returns None.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.  The new ``PriceHistory`` row is added
        with ``db.add()`` but the session is NOT committed.
    subscription:
        The newly created subscription.
    amount:
        The initial price (Decimal, float, or int).
    currency:
        ISO-4217 currency code, e.g. ``"EUR"``.
    detected_from:
        Source of detection.
    notes:
        Free-text notes stored on the record.
    sync_history_id:
        Optional FK to ``sync_history.id`` identifying the sync run that
        produced this initial-price record. ``None`` for non-sync paths.

    Returns
    -------
    PriceHistory | None
        The newly created (but not yet committed) record, or ``None`` if
        amount was None.
    """
    if amount is None:
        return None

    record = PriceHistory(
        subscription_id=subscription.id,
        old_amount=None,  # No previous price for initial record
        new_amount=amount,
        currency=currency,
        change_type="initial",
        change_percentage=None,  # No percentage for initial record
        detected_from=detected_from,
        notes=notes,
        sync_history_id=sync_history_id,
    )
    db.add(record)
    logger.info(
        f"Initial price recorded for {subscription.provider}: {amount} {currency}"
    )
    return record
