"""Pure helper utilities for the email-sync pipeline.

Contains:
  - ``VALID_SUBSCRIPTION_FIELDS``: the whitelist of model attributes that
    AI extraction is allowed to set on ``Subscription`` rows.
  - ``filter_subscription_data``: drops metadata-only keys (e.g.
    ``is_price_update``) before they reach the ORM.
  - ``parse_date_filter``: parses date-filter strings (``"30days"`` etc.)
    into a UTC ``datetime``.

This module is intentionally a leaf in the import DAG — it depends only
on stdlib and ``app.config`` / ``app.utils.config_helper``.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.config import settings
from app.utils.config_helper import get_config_value


# Fields that are valid for the Subscription model
# Used to filter out metadata fields from AI extraction (e.g., is_price_update, old_amount, new_amount)
VALID_SUBSCRIPTION_FIELDS = {
    "provider",
    "email_sender",
    "amount",
    "currency",
    "billing_cycle",
    "renewal_date",
    "next_billing_date",
    "is_active",
    "manual_status_override",
    "trial_status",
    "trial_end_date",
    "is_confirmed",
    "category",
    "tags",
    "custom_label",
    "notes",
    "cancellation_status",
    "cancellation_requested_at",
    "cancellation_confirmed_at",
    "cancellation_notes",
    "suggested_cancellation_status",
    "cancellation_suggestion_reason",
    "cancellation_suggestion_created_at",
    "confidence_score",
    "extraction_method",
    "extraction_metadata",
    "payment_processor",
}


def filter_subscription_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Filter subscription data to only include valid model fields."""
    return {k: v for k, v in data.items() if k in VALID_SUBSCRIPTION_FIELDS}


def parse_date_filter(filter_str: str, db: Session = None) -> datetime:
    """
    Parse date filter string into datetime.

    Supported formats:
    - '30days', '60days', '90days', '365days'
    - '1month', '3months', '6months', '12months'
    - '1year', '2years'

    Args:
        filter_str: Date filter string
        db: Optional database session for admin config lookup
    """
    filter_str = filter_str.lower().strip()
    now = datetime.now(timezone.utc)

    if "day" in filter_str:
        days = int(filter_str.replace("days", "").replace("day", ""))
        return now - timedelta(days=days)
    elif "month" in filter_str:
        months = int(filter_str.replace("months", "").replace("month", ""))
        return now - timedelta(days=months * 30)
    elif "year" in filter_str:
        years = int(filter_str.replace("years", "").replace("year", ""))
        return now - timedelta(days=years * 365)
    else:
        # Use configurable default sync period (admin panel or env)
        default_days = get_config_value(
            "email.default_sync_period_days", settings.DEFAULT_SYNC_PERIOD_DAYS, db
        )
        return now - timedelta(days=default_days)
