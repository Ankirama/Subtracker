"""
Diagnostic script to check Gmail sync pagination issue.

Run in production:
docker exec subscriptions_backend python check_gmail_sync.py YOUR_MAILBOX_ID
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models.mailbox import Mailbox
from app.models.sync_history import SyncHistory
from app.models.email_message import EmailMessage
from sqlalchemy import desc


def check_gmail_sync(mailbox_id: str):
    """Check Gmail sync stats and identify pagination issues."""
    db = SessionLocal()

    try:
        # Get mailbox
        mailbox = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
        if not mailbox:
            print(f"❌ Mailbox {mailbox_id} not found")
            return

        print(f"\n{'='*60}")
        print(f"📧 Mailbox: {mailbox.email_address}")
        print(f"   Provider: {mailbox.provider_type}")
        print(f"   Batch Size: {mailbox.batch_size}")
        print(f"   Import Filter: {mailbox.import_date_filter}")
        print(f"{'='*60}\n")

        # Get latest sync history
        latest_sync = (
            db.query(SyncHistory)
            .filter(SyncHistory.mailbox_id == mailbox_id)
            .order_by(desc(SyncHistory.started_at))
            .first()
        )

        if latest_sync:
            print("📊 Latest Sync Stats:")
            print(f"   Status: {latest_sync.status}")
            print(f"   Started: {latest_sync.started_at}")
            print(f"   Completed: {latest_sync.completed_at}")
            print(f"   Emails Processed: {latest_sync.emails_processed}")
            print(f"   Subscriptions Found: {latest_sync.subscriptions_found}")
            print(
                f"   Duration: {(latest_sync.completed_at - latest_sync.started_at).total_seconds():.1f}s"
            )
            print()

        # Count total emails for this mailbox
        total_emails = (
            db.query(EmailMessage).filter(EmailMessage.mailbox_id == mailbox_id).count()
        )

        print(f"📨 Total Emails in DB: {total_emails}")

        # Check if emails match expected for time period
        if mailbox.import_date_filter:
            filter_parts = mailbox.import_date_filter.split("_")
            if len(filter_parts) == 2:
                value, unit = int(filter_parts[0]), filter_parts[1]
                print(f"   Filter: Last {value} {unit}")

                # Estimate expected emails
                if unit == "days":
                    days = value
                else:  # months or years
                    days = value * 30 if unit == "months" else value * 365

                # Average person gets 120-150 emails per day
                estimated_min = days * 50  # Conservative estimate
                estimated_max = days * 150

                print(
                    f"   Expected Range: {estimated_min:,} - {estimated_max:,} emails"
                )
                print()

                if total_emails < estimated_min:
                    print("⚠️  ISSUE DETECTED: Email count is MUCH lower than expected!")
                    print()

        # Check batching pattern
        if latest_sync and latest_sync.emails_processed:
            batch_count = (latest_sync.emails_processed // mailbox.batch_size) + 1
            print("🔍 Pagination Analysis:")
            print(f"   Batch Size: {mailbox.batch_size}")
            print(f"   Emails Processed: {latest_sync.emails_processed}")
            print(f"   Expected Batches: ≥{batch_count}")
            print()

            # Check if it's suspiciously close to one batch
            if latest_sync.emails_processed <= mailbox.batch_size:
                print("❌ PAGINATION BUG CONFIRMED!")
                print(f"   Only fetched {latest_sync.emails_processed} emails")
                print(f"   This is ≤ batch_size ({mailbox.batch_size})")
                print("   Indicates pagination stopped after first batch")
                print()
                print("🔧 Root Cause:")
                print("   Gmail provider's fetch_messages() doesn't implement")
                print("   pageToken-based pagination. It returns has_more=False")
                print("   after the first batch, breaking the pagination loop.")
                print()
                print("📝 See: backend/app/email_providers/gmail.py:198-200")
                print()

        # Recent emails by date
        recent_emails = (
            db.query(EmailMessage.date)
            .filter(EmailMessage.mailbox_id == mailbox_id)
            .order_by(desc(EmailMessage.date))
            .limit(5)
            .all()
        )

        if recent_emails:
            print("📅 Most Recent Emails Synced:")
            for email in recent_emails:
                print(f"   {email[0]}")
            print()

        oldest_email = (
            db.query(EmailMessage.date)
            .filter(EmailMessage.mailbox_id == mailbox_id)
            .order_by(EmailMessage.date)
            .first()
        )

        if oldest_email:
            print(f"📅 Oldest Email Synced: {oldest_email[0]}")
            print()

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_gmail_sync.py MAILBOX_ID")
        print("\nTo get mailbox ID, run:")
        print(
            "  docker exec subscriptions_postgres psql -U subscriptions -d subscriptions \\"
        )
        print(
            "    -c \"SELECT id, email_address FROM mailboxes WHERE provider_type='gmail';\""
        )
        sys.exit(1)

    mailbox_id = sys.argv[1]
    check_gmail_sync(mailbox_id)
