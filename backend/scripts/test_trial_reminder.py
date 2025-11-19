"""
Test script for trial reminder functionality.

Creates a test subscription with trial ending soon and triggers the reminder task.
"""
import sys
import os
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription
from app.models.notification import Notification, NotificationType
from app.tasks.trial_reminders import check_trial_reminders
from app.security.password import hash_password


def create_test_data():
    """Create test user and subscription with trial ending soon."""
    db = SessionLocal()
    try:
        # Check if test user exists
        test_user = db.query(User).filter(User.email == "bother@ankirama.com").first()

        if not test_user:
            print("Creating test user...")
            password_hash, salt = hash_password("testpassword123")
            test_user = User(
                email="bother@ankirama.com",
                password_hash=password_hash,
                salt=salt,
                is_active=True
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"✅ Created test user: {test_user.email} (ID: {test_user.id})")
        else:
            print(f"✅ Test user exists: {test_user.email} (ID: {test_user.id})")

        # Create test subscriptions with different trial end dates
        test_cases = [
            (3, "Netflix", 15.99, "streaming"),
            (1, "Spotify", 9.99, "music"),
            (0, "Adobe Creative Cloud", 54.99, "software"),
        ]

        created_subs = []
        for days_until_end, provider, amount, category in test_cases:
            trial_end_date = date.today() + timedelta(days=days_until_end)

            # Check if subscription already exists
            existing = db.query(Subscription).filter(
                Subscription.user_id == test_user.id,
                Subscription.provider == provider,
                Subscription.trial_end_date == trial_end_date
            ).first()

            if not existing:
                subscription = Subscription(
                    user_id=test_user.id,
                    provider=provider,
                    amount=amount,
                    currency="USD",
                    billing_cycle="monthly",
                    category=category,
                    is_active=True,
                    trial_status="trial",
                    trial_end_date=trial_end_date,
                    first_detected_at=datetime.now(timezone.utc)
                )
                db.add(subscription)
                db.commit()
                db.refresh(subscription)
                created_subs.append((subscription, days_until_end))
                print(f"✅ Created {provider} trial ending in {days_until_end} days (ID: {subscription.id})")
            else:
                created_subs.append((existing, days_until_end))
                print(f"✅ Using existing {provider} trial ending in {days_until_end} days (ID: {existing.id})")

        return test_user, created_subs

    finally:
        db.close()


def run_test():
    """Run the trial reminder test."""
    print("\n" + "="*70)
    print("TRIAL REMINDER SYSTEM TEST")
    print("="*70 + "\n")

    # Step 1: Create test data
    print("📝 Step 1: Creating test data...")
    test_user, test_subscriptions = create_test_data()
    test_user_id = test_user.id  # Store the ID before session closes
    print(f"\n✅ Test data ready: {len(test_subscriptions)} subscriptions with trials ending soon\n")

    # Step 2: Check current notifications
    db = SessionLocal()
    try:
        existing_notifications = db.query(Notification).filter(
            Notification.user_id == test_user_id,
            Notification.type == NotificationType.TRIAL_ENDING
        ).count()
        print(f"📊 Current trial notifications for user: {existing_notifications}")
    finally:
        db.close()

    # Step 3: Run the trial reminder task
    print("\n🚀 Step 2: Running trial reminder task...")
    print("-" * 70)

    result = check_trial_reminders()

    print("-" * 70)
    print("\n📊 Task Result:")
    print(f"   Status: {result.get('status', 'unknown')}")
    print(f"   Notifications Created: {result.get('notifications_created', 0)}")
    print(f"   Emails Sent: {result.get('emails_sent', 0)}")

    if result.get('status') == 'error':
        print(f"   ❌ Error: {result.get('error', 'Unknown error')}")

    # Step 4: Check created notifications
    print("\n📝 Step 3: Checking created notifications...")
    db = SessionLocal()
    try:
        notifications = db.query(Notification).filter(
            Notification.user_id == test_user_id,
            Notification.type == NotificationType.TRIAL_ENDING
        ).order_by(Notification.created_at.desc()).limit(10).all()

        print(f"\n✅ Found {len(notifications)} trial ending notifications:")
        for notif in notifications:
            related_sub = db.query(Subscription).filter(
                Subscription.id == notif.related_subscription_id
            ).first()

            days_data = notif.notification_metadata.get('days_before', 'unknown')
            print(f"\n   📧 Notification ID: {notif.id}")
            print(f"      Provider: {related_sub.provider if related_sub else 'Unknown'}")
            print(f"      Priority: {notif.priority}")
            print(f"      Days Before: {days_data}")
            print(f"      Email Sent: {'✅ Yes' if notif.email_sent else '❌ No'}")
            if notif.email_error:
                print(f"      Email Error: {notif.email_error}")
            print(f"      Created: {notif.created_at}")

        # Check SendGrid configuration
        print("\n⚙️  SendGrid Configuration:")
        from app.config import settings
        api_key = settings.SENDGRID_API_KEY
        if api_key == "your_sendgrid_api_key_here":
            print("   ⚠️  WARNING: SendGrid API key is not configured!")
            print("   📝 Emails will fail until you set a valid API key")
            print("   💡 Set SENDGRID_API_KEY environment variable or use admin API")
        else:
            masked_key = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 15 else "***"
            print(f"   ✅ API Key: {masked_key}")

        print(f"   📧 From Email: {settings.SENDGRID_FROM_EMAIL}")
        print(f"   📝 From Name: {settings.SENDGRID_FROM_NAME}")

    finally:
        db.close()

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")

    # Cleanup instructions
    print("🧹 Cleanup (optional):")
    print(f"   To delete test user and subscriptions, run:")
    print(f'   python -c "from app.database import SessionLocal; from app.models.user import User; db = SessionLocal(); user = db.query(User).filter(User.email==\\"bother@ankirama.com\\").first(); db.delete(user) if user else None; db.commit(); print(\\"Cleaned up\\")"')
    print()


if __name__ == "__main__":
    try:
        run_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
