#!/usr/bin/env python3
"""
Batch recalculation script for subscription renewal dates and statuses.
Runs the renewal calculator logic on all existing subscriptions.

This script should be run:
1. After updating the renewal calculation logic
2. When fixing historical data issues
3. As a maintenance task to ensure data accuracy

Usage:
    # From project root
    docker exec subscriptions_backend python scripts/recalculate_renewals.py
"""

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.subscription import Subscription
from app.services.renewal_calculator import RenewalCalculator, get_subscription_emails
from datetime import datetime

def recalculate_all_subscriptions():
    """Recalculate renewal dates and statuses for all subscriptions."""
    db: Session = SessionLocal()
    try:
        # Get all subscriptions
        subscriptions = db.query(Subscription).all()
        total = len(subscriptions)
        updated = 0
        skipped = 0
        errors = 0

        print(f"Found {total} subscriptions to process\n")

        renewal_calc = RenewalCalculator(db)

        for idx, subscription in enumerate(subscriptions, 1):
            print(f"[{idx}/{total}] Processing: {subscription.provider} (ID: {subscription.id})")

            try:
                # Get all emails for this subscription
                subscription_emails_data = get_subscription_emails(db, subscription.id)

                if not subscription_emails_data:
                    print(f"  ⚠️  No emails found, skipping")
                    skipped += 1
                    continue

                # Extract dates and contents
                email_dates = [e['date'] for e in subscription_emails_data]
                email_contents = [e['body_html'] or e['body_text'] or '' for e in subscription_emails_data]

                # Store old values for comparison
                old_renewal = subscription.renewal_date
                old_active = subscription.is_active
                old_trial = subscription.trial_status
                old_confirmed = subscription.is_confirmed

                # Calculate new values
                renewal_date, is_active, trial_status, is_confirmed = renewal_calc.calculate_renewal_info(
                    provider=subscription.provider,
                    billing_cycle=subscription.billing_cycle,
                    email_dates=email_dates,
                    email_contents=email_contents,
                    extraction_metadata=subscription.extraction_metadata
                )

                # Check if anything changed
                changed = False
                changes = []

                if renewal_date and renewal_date != old_renewal:
                    subscription.renewal_date = renewal_date
                    changes.append(f"renewal: {old_renewal} → {renewal_date.strftime('%Y-%m-%d')}")
                    changed = True

                if is_active != old_active:
                    subscription.is_active = is_active
                    changes.append(f"active: {old_active} → {is_active}")
                    changed = True

                if trial_status != old_trial:
                    subscription.trial_status = trial_status
                    changes.append(f"trial: {old_trial} → {trial_status}")
                    changed = True

                if is_confirmed != old_confirmed:
                    subscription.is_confirmed = is_confirmed
                    changes.append(f"confirmed: {old_confirmed} → {is_confirmed}")
                    changed = True

                if changed:
                    print(f"  ✅ Updated: {', '.join(changes)}")
                    updated += 1
                else:
                    print(f"  ➡️  No changes needed")
                    skipped += 1

            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
                errors += 1
                continue

        # Commit all changes
        db.commit()

        print(f"\n{'='*60}")
        print(f"Recalculation complete!")
        print(f"  Total subscriptions: {total}")
        print(f"  Updated: {updated}")
        print(f"  Skipped (no changes): {skipped}")
        print(f"  Errors: {errors}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"Fatal error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    recalculate_all_subscriptions()
