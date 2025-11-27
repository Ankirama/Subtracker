"""
Test script for new notification types: price changes and system announcements.

Tests:
1. Price change detection and notification
2. System announcement broadcast
"""

import sys
import os
from pathlib import Path
from decimal import Decimal
import requests
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription
from app.models.notification import Notification, NotificationType
from app.tasks.price_change_monitor import check_price_changes
from app.security.password import hash_password
from datetime import date, timedelta, datetime, timezone


def get_admin_token():
    """Get admin token for API requests."""
    # Create admin user if doesn't exist
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "bother@ankirama.com").first()
        if not admin:
            print("Admin user not found, creating...")
            password_hash, salt = hash_password("testpassword123")
            admin = User(
                email="bother@ankirama.com",
                password_hash=password_hash,
                salt=salt,
                is_active=True,
                is_admin=True,
            )
            db.add(admin)
            db.commit()
            print(f"✅ Created admin user: {admin.email}")

        # Make sure user is admin
        if not admin.is_admin:
            admin.is_admin = True
            db.commit()
            print(f"✅ Updated {admin.email} to admin")

        admin_id = admin.id
    finally:
        db.close()

    # Login to get token
    response = requests.post(
        "http://localhost:8000/api/auth/login",
        json={"email": "bother@ankirama.com", "password": "testpassword123"},
    )

    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Got admin token: {token[:20]}...")
        return token
    else:
        print(f"❌ Failed to get token: {response.status_code}")
        print(f"   Response: {response.text}")
        return None


def test_price_change_notifications():
    """Test price change detection and notifications."""
    print("\n" + "=" * 70)
    print("TEST 1: PRICE CHANGE NOTIFICATIONS")
    print("=" * 70 + "\n")

    db = SessionLocal()
    try:
        # Get test user
        test_user = db.query(User).filter(User.email == "bother@ankirama.com").first()
        if not test_user:
            print("❌ Test user not found")
            return False

        print(f"📝 Using test user: {test_user.email} (ID: {test_user.id})")

        # Create a subscription with initial price
        print("\n📝 Step 1: Creating test subscription with initial price...")

        test_sub = Subscription(
            user_id=test_user.id,
            provider="Netflix Premium",
            amount=Decimal("15.99"),
            currency="USD",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            next_billing_date=date.today() + timedelta(days=15),
            first_detected_at=datetime.now(timezone.utc),
            extraction_metadata={},  # Empty metadata
        )
        db.add(test_sub)
        db.commit()
        db.refresh(test_sub)
        print(f"✅ Created subscription: {test_sub.provider} at ${test_sub.amount}")

        # Run price check (should initialize last_known_price)
        print("\n📝 Step 2: Running initial price check (should store baseline)...")
        result = check_price_changes()
        print(f"   Result: {result}")

        # Refresh to get updated metadata
        db.refresh(test_sub)
        print(f"   Metadata: {test_sub.extraction_metadata}")

        # Change the price
        print("\n📝 Step 3: Simulating price increase...")
        new_price = Decimal("17.99")
        test_sub.amount = new_price
        db.commit()
        print(f"✅ Updated price: ${new_price} (was $15.99)")

        # Run price check again (should detect change)
        print("\n📝 Step 4: Running price check (should detect change)...")
        result = check_price_changes()
        print(f"   Result: {result}")
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

        print(f"✅ Found {len(price_notifications)} price change notification(s):")
        for notif in price_notifications:
            metadata = notif.notification_metadata
            print(f"\n   📧 Notification ID: {notif.id}")
            print(f"      Title: {notif.title}")
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


def test_system_announcements():
    """Test system announcement broadcast."""
    print("\n" + "=" * 70)
    print("TEST 2: SYSTEM ANNOUNCEMENTS")
    print("=" * 70 + "\n")

    # Get admin token
    token = get_admin_token()
    if not token:
        print("❌ Failed to get admin token")
        return False

    # Create system announcement
    print("\n📝 Step 1: Broadcasting system announcement...")

    announcement_data = {
        "title": "Test System Announcement",
        "message": "This is a test announcement to verify the system works correctly. All users should receive this notification.",
        "priority": "high",
        "target_all_users": True,
    }

    response = requests.post(
        "http://localhost:8000/api/admin/announcements/broadcast",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=announcement_data,
    )

    if response.status_code == 201:
        result = response.json()
        print(f"✅ Announcement broadcast initiated:")
        print(f"   Announcement ID: {result['announcement_id']}")
        print(f"   Message: {result['message']}")
    else:
        print(f"❌ Failed to broadcast announcement: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

    # Wait for task to complete
    print("\n⏳ Waiting 5 seconds for broadcast task to complete...")
    import time

    time.sleep(5)

    # Check notifications
    print("\n📝 Step 2: Checking created notifications...")
    db = SessionLocal()
    try:
        announcement_notifications = (
            db.query(Notification)
            .filter(Notification.type == NotificationType.SYSTEM_ANNOUNCEMENT)
            .order_by(Notification.created_at.desc())
            .limit(10)
            .all()
        )

        print(
            f"✅ Found {len(announcement_notifications)} system announcement notification(s):"
        )
        for notif in announcement_notifications[:3]:  # Show first 3
            metadata = notif.notification_metadata
            user = db.query(User).filter(User.id == notif.user_id).first()
            print(f"\n   📧 Notification ID: {notif.id}")
            print(f"      User: {user.email if user else 'Unknown'}")
            print(f"      Title: {notif.title}")
            print(f"      Priority: {notif.priority}")
            print(f"      Email Sent: {'✅ Yes' if notif.email_sent else '❌ No'}")
            if notif.email_error:
                print(f"      Email Error: {notif.email_error}")

        return len(announcement_notifications) > 0

    except Exception as e:
        print(f"\n❌ Error checking notifications: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def run_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("NEW NOTIFICATION TYPES TEST SUITE")
    print("=" * 70 + "\n")

    results = {}

    # Test 1: Price Changes
    try:
        results["price_change"] = test_price_change_notifications()
    except Exception as e:
        print(f"\n❌ Price change test failed: {e}")
        results["price_change"] = False

    # Test 2: System Announcements
    try:
        results["announcements"] = test_system_announcements()
    except Exception as e:
        print(f"\n❌ System announcement test failed: {e}")
        results["announcements"] = False

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(
        f"✅ Price Change Notifications: {'PASS' if results.get('price_change') else 'FAIL'}"
    )
    print(
        f"✅ System Announcements: {'PASS' if results.get('announcements') else 'FAIL'}"
    )
    print("=" * 70 + "\n")

    return all(results.values())


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
