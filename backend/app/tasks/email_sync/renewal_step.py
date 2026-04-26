"""Renewal calculation step for the email-sync pipeline.

Wraps ``app.services.renewal_calculator.RenewalCalculator`` and the
helper ``get_subscription_emails`` to produce the renewal date, active
status, trial status, and confirmation flag for a freshly-upserted
subscription. Best-effort: an exception inside ``RenewalCalculator``
must NOT abort batch processing (the orchestrator catches a generic
``Exception`` around the call).

Mirrors the inline block previously at ``_sync_mailbox_async`` lines
560-627 (pre-Phase-8b numbering). Does NOT commit; the caller controls
transaction boundaries.

The ``RenewalCalculator`` reference is kept module-level (not lazy)
because tests monkeypatch the symbol via
``patch("app.tasks.email_sync.RenewalCalculator")`` — re-exported in
``__init__.py`` for back-compat.
"""

import logging

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.services.renewal_calculator import RenewalCalculator, get_subscription_emails

logger = logging.getLogger(__name__)


def calculate_renewal_for_subscription(
    db: Session, subscription_record: Subscription
) -> None:
    """Compute and apply renewal info onto a freshly upserted subscription.

    Best-effort: catches any ``Exception`` so a calculation failure on a
    single subscription does not abort the per-batch processing loop.
    Mutates ``subscription_record`` in place (sets ``renewal_date``,
    ``is_active``, ``trial_status``, ``is_confirmed``) and may flush the
    session, but never commits.
    """
    try:
        # Flush to ensure we can query for subscription emails
        db.flush()

        # Get all emails for this subscription
        subscription_emails_data = get_subscription_emails(db, subscription_record.id)

        if subscription_emails_data:
            # Extract dates and contents
            email_dates = [e["date"] for e in subscription_emails_data]
            email_contents = [
                e["body_html"] or e["body_text"] or "" for e in subscription_emails_data
            ]

            # Initialize renewal calculator
            renewal_calc = RenewalCalculator(db)

            # Calculate renewal date, active status, trial status, and confirmation
            (
                renewal_date,
                is_active,
                trial_status,
                is_confirmed,
            ) = renewal_calc.calculate_renewal_info(
                provider=subscription_record.provider,
                billing_cycle=subscription_record.billing_cycle,
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=subscription_record.extraction_metadata,
            )

            # Update subscription with calculated values
            if renewal_date:
                subscription_record.renewal_date = renewal_date
                logger.info(
                    f"Calculated renewal date for {subscription_record.provider}: {renewal_date.strftime('%Y-%m-%d')}"
                )

            subscription_record.is_active = is_active
            subscription_record.trial_status = trial_status
            subscription_record.is_confirmed = is_confirmed
            logger.info(
                f"Set status for {subscription_record.provider}: active={is_active}, trial={trial_status}, confirmed={is_confirmed}"
            )

            # Detect if this is a reactivation
            is_reactivation = renewal_calc.detect_reactivation(
                email_dates=email_dates,
                billing_cycle=subscription_record.billing_cycle,
            )

            if is_reactivation:
                logger.info(f"Reactivation detected for {subscription_record.provider}")

    except Exception as e:
        logger.error(
            f"Error calculating renewal date for {subscription_record.provider}: {str(e)}"
        )
        # Continue with subscription creation even if renewal calculation fails
