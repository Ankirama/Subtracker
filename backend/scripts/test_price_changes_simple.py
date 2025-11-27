"""
Simple test script for price change notifications.

Tests price change detection directly without using API calls.
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription
from app.models.notification import Notification, NotificationType
from app.tasks.price_change_monitor import check_price_changes
from app.security.password import hash_password
from datetime import date, timedelta, datetime, timezone


def run_test():
    """Test price change detection."""
    print("\n" + "=" * 70)
    print("PRICE CHANGE NOTIFICATION TEST")
    print("=" * 70 + "\n")

    db = SessionLocal()
    try:
        # Get test user
        test_user = db.query(User).filter(User.email == "bother@ankirama.com").first()
        if not test_user:
            print("Creating test user...")
            password_hash, salt = hash_password("testpassword123")
            test_user = User(
                email="bother@ankirama.com",
                password_hash=password_hash,
                salt=salt,
                is_active=True,
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"✅ Created test user: {test_user.email}")

        print(f"📝 Using test user: {test_user.email} (ID: {test_user.id})")

        # Create a subscription with initial price
        print("\n📝 Step 1: Creating test subscription with initial price...")
        test_sub = Subscription(
            user_id=test_user.id,
            provider="Netflix Premium (Test)",
            amount=Decimal("15.99"),
            currency="USD",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            next_billing_date=date.today() + timedelta(days=15),
            first_detected_at=datetime.now(timezone.utc),
            extraction_metadata={},
        )
        db.add(test_sub)
        db.commit()
        db.refresh(test_sub)
        print(f"✅ Created subscription: {test_sub.provider} at ${test_sub.amount}")

        # Run initial price check
        print("\n📝 Step 2: Running initial price check (should store baseline)...")
        result = check_price_changes()
        print(f"   Result: {result}")

        db.refresh(test_sub)
        last_known = test_sub.extraction_metadata.get("last_known_price")
        print(f"   ✅ Stored baseline price: ${last_known}")

        # Change the price
        print("\n📝 Step 3: Simulating price increase...")
        new_price = Decimal("17.99")
        test_sub.amount = new_price
        db.commit()
        print(f"✅ Updated price: ${new_price} (was $15.99)")

        # Run price check again
        print("\n📝 Step 4: Running price check (should detect change)...")
        result = check_price_changes()
        print("\n📊 Task Result:")
        print(f"   Status: {result.get('status')}")
        print(f"   Changes detected: {result.get('price_changes_detected', 0)}")
        print(f"   Notifications created: {result.get('notifications_created', 0)}")
        print(f"   Emails sent: {result.get('emails_sent', 0)}")

        # Check notifications
        print("\n📝 Step 5: Checking created notifications...")
        price_notifications = (
            db.query(Notification)
            .filter(
                Notification.user_id == test_user.id,
                Notification.type == NotificationType.PRICE_CHANGE,
            )
            .order_by(Notification.created_at.desc())
            .limit(5)
            .all()
        )

        print(f"\n✅ Found {len(price_notifications)} price change notification(s):")
        for notif in price_notifications:
            metadata = notif.notification_metadata
            print(f"\n   📧 Notification ID: {notif.id}")
            print(f"      Title: {notif.title}")
            print(f"      Message: {notif.message[:100]}...")
            print(f"      Priority: {notif.priority}")
            print(f"      Old Price: ${metadata.get('old_price')}")
            print(f"      New Price: ${metadata.get('new_price')}")
            print(
                f"      Change: ${metadata.get('price_difference')} ({metadata.get('change_percent'):.1f}%)"
            )
            print(f"      Is Increase: {metadata.get('is_increase')}")
            print(f"      Email Sent: {'✅ Yes' if notif.email_sent else '❌ No'}")
            if notif.email_error:
                print(f"      Email Error: {notif.email_error}")

        # Cleanup
        print("\n🧹 Cleaning up test subscription...")
        db.delete(test_sub)
        db.commit()
        print("✅ Cleanup complete")

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        if (
            result.get("status") == "success"
            and result.get("price_changes_detected", 0) > 0
        ):
            print("✅ TEST PASSED - Price change detected and notifications created!")
        else:
            print("❌ TEST FAILED - No price changes detected")
        print("=" * 70 + "\n")

        return (
            result.get("status") == "success"
            and result.get("price_changes_detected", 0) > 0
        )

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    try:
        success = run_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
