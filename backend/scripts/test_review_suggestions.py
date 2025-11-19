#!/usr/bin/env python3
"""
Test script for ReviewSuggestionsService.
Creates test subscriptions and validates suggestion algorithm.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from decimal import Decimal

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import SessionLocal
from app.models.subscription import Subscription
from app.models.user import User
from app.models.mailbox import Mailbox
from app.models.email_message import EmailMessage, subscription_emails
from app.services.review_suggestions import ReviewSuggestionsService
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_subscriptions(db: Session, user_id, mailbox_id):
    """Create test subscriptions with various conditions"""

    logger.info("Creating test subscriptions...")

    # 1. Trial ending TODAY (CRITICAL)
    sub1 = Subscription(
        user_id=user_id,
        mailbox_id=mailbox_id,
        provider="Netflix",
        amount=Decimal("15.99"),
        currency="USD",
        billing_cycle="monthly",
        trial_status="trial",
        trial_end_date=date.today(),
        is_active=True,
        cancellation_status="active"
    )
    db.add(sub1)

    # 2. Trial ending in 2 days (HIGH)
    sub2 = Subscription(
        user_id=user_id,
        mailbox_id=mailbox_id,
        provider="Spotify",
        amount=Decimal("9.99"),
        currency="USD",
        billing_cycle="monthly",
        trial_status="trial",
        trial_end_date=date.today() + timedelta(days=2),
        is_active=True,
        cancellation_status="active"
    )
    db.add(sub2)

    # 3. Expensive unused (HIGH)
    sub3 = Subscription(
        user_id=user_id,
        mailbox_id=mailbox_id,
        provider="Adobe Creative Cloud",
        amount=Decimal("54.99"),
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        cancellation_status="active"
    )
    db.add(sub3)
    db.flush()

    # Add old email to sub3 (no recent activity)
    old_email = EmailMessage(
        mailbox_id=mailbox_id,
        message_id=f"test-adobe-{datetime.utcnow().timestamp()}",
        subject="Adobe Receipt",
        sender="noreply@adobe.com",
        recipient="test@example.com",
        date=datetime.utcnow() - timedelta(days=45),
        body_text="Your Adobe subscription has been renewed"
    )
    db.add(old_email)
    db.flush()

    # Link email to subscription
    link = subscription_emails.insert().values(
        subscription_id=sub3.id,
        email_id=old_email.id,
        extraction_role="renewal"
    )
    db.execute(link)

    # 4. Duplicate provider (MEDIUM) - first one
    sub4 = Subscription(
        user_id=user_id,
        mailbox_id=mailbox_id,
        provider="Dropbox",
        amount=Decimal("11.99"),
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        cancellation_status="active"
    )
    db.add(sub4)

    # 5. Duplicate provider (MEDIUM) - second one
    sub5 = Subscription(
        user_id=user_id,
        mailbox_id=mailbox_id,
        provider="Dropbox",
        amount=Decimal("9.99"),
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        cancellation_status="active"
    )
    db.add(sub5)

    # 6. Likely unused (MEDIUM)
    sub6 = Subscription(
        user_id=user_id,
        mailbox_id=mailbox_id,
        provider="LinkedIn Premium",
        amount=Decimal("29.99"),
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        cancellation_status="active"
    )
    db.add(sub6)
    db.flush()

    # Add old email to sub6
    old_email2 = EmailMessage(
        mailbox_id=mailbox_id,
        message_id=f"test-linkedin-{datetime.utcnow().timestamp()}",
        subject="LinkedIn Receipt",
        sender="noreply@linkedin.com",
        recipient="test@example.com",
        date=datetime.utcnow() - timedelta(days=35),
        body_text="Your LinkedIn Premium subscription"
    )
    db.add(old_email2)
    db.flush()

    link2 = subscription_emails.insert().values(
        subscription_id=sub6.id,
        email_id=old_email2.id,
        extraction_role="renewal"
    )
    db.execute(link2)

    # 7. Active subscription with recent email (NO SUGGESTION)
    sub7 = Subscription(
        user_id=user_id,
        mailbox_id=mailbox_id,
        provider="GitHub",
        amount=Decimal("4.00"),
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        cancellation_status="active"
    )
    db.add(sub7)
    db.flush()

    # Add recent email to sub7
    recent_email = EmailMessage(
        mailbox_id=mailbox_id,
        message_id=f"test-github-{datetime.utcnow().timestamp()}",
        subject="GitHub Receipt",
        sender="noreply@github.com",
        recipient="test@example.com",
        date=datetime.utcnow() - timedelta(days=2),
        body_text="Your GitHub subscription"
    )
    db.add(recent_email)
    db.flush()

    link3 = subscription_emails.insert().values(
        subscription_id=sub7.id,
        email_id=recent_email.id,
        extraction_role="renewal"
    )
    db.execute(link3)

    db.commit()
    logger.info("✅ Created 7 test subscriptions")

    return {
        "trial_today": sub1.id,
        "trial_soon": sub2.id,
        "expensive_unused": sub3.id,
        "duplicate1": sub4.id,
        "duplicate2": sub5.id,
        "unused": sub6.id,
        "active": sub7.id
    }


def cleanup_test_subscriptions(db: Session, user_id):
    """Clean up test subscriptions"""
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    subscriptions = db.execute(stmt).scalars().all()

    for sub in subscriptions:
        # Delete linked emails
        for email in sub.source_emails:
            db.delete(email)
        db.delete(sub)

    db.commit()
    logger.info(f"✅ Cleaned up {len(subscriptions)} test subscriptions")


def main():
    """Run review suggestions tests"""
    db = SessionLocal()

    try:
        logger.info("🧪 Starting ReviewSuggestionsService Tests\n")

        # Get test user
        stmt = select(User).limit(1)
        user = db.execute(stmt).scalar_one_or_none()

        if not user:
            logger.error("❌ No users found in database")
            return 1

        logger.info(f"Using test user: {user.email}")

        # Get or create test mailbox
        stmt = select(Mailbox).where(Mailbox.user_id == user.id).limit(1)
        mailbox = db.execute(stmt).scalar_one_or_none()

        if not mailbox:
            logger.error("❌ No mailbox found for user")
            return 1

        # Clean up any existing test subscriptions
        cleanup_test_subscriptions(db, user.id)

        # Create test subscriptions
        test_subs = create_test_subscriptions(db, user.id, mailbox.id)

        # Test the service
        logger.info("\n" + "="*80)
        logger.info("Testing ReviewSuggestionsService.get_review_suggestions()")
        logger.info("="*80 + "\n")

        service = ReviewSuggestionsService(db)
        result = service.get_review_suggestions(user.id)

        # Display results
        print("\n" + "="*80)
        print(f"📊 REVIEW SUGGESTIONS RESULTS")
        print("="*80)
        print(f"Total suggestions: {result.total_count}")
        print(f"Critical: {result.critical_count}")
        print(f"High priority: {result.high_priority_count}")
        print()

        if result.suggestions:
            for i, suggestion in enumerate(result.suggestions, 1):
                priority_emoji = {
                    'critical': '🚨',
                    'high': '⚠️',
                    'medium': '💡',
                    'low': 'ℹ️'
                }

                print(f"{i}. {priority_emoji.get(suggestion.priority, '•')} [{suggestion.priority.upper()}] {suggestion.provider}")
                print(f"   Reason: {suggestion.reason.value}")
                print(f"   Message: {suggestion.message}")
                if suggestion.action_by_date:
                    print(f"   Action by: {suggestion.action_by_date.strftime('%Y-%m-%d')}")
                print()

        # Validation
        print("="*80)
        print("📋 VALIDATION")
        print("="*80)

        expected_count = 6  # 7 subscriptions - 1 active with recent email
        if result.total_count == expected_count:
            print(f"✅ Expected {expected_count} suggestions, got {expected_count}")
        else:
            print(f"❌ Expected {expected_count} suggestions, got {result.total_count}")

        if result.critical_count >= 1:
            print(f"✅ Found {result.critical_count} critical suggestion(s) (trial ending today)")
        else:
            print(f"❌ Expected at least 1 critical suggestion")

        if result.high_priority_count >= 2:
            print(f"✅ Found {result.high_priority_count} high priority suggestion(s)")
        else:
            print(f"❌ Expected at least 2 high priority suggestions")

        # Check specific suggestions
        providers_found = {s.provider for s in result.suggestions}
        expected_providers = {"Netflix", "Spotify", "Adobe Creative Cloud", "Dropbox", "LinkedIn Premium"}

        if expected_providers.issubset(providers_found):
            print(f"✅ Found all expected providers in suggestions")
        else:
            missing = expected_providers - providers_found
            print(f"❌ Missing providers: {missing}")

        print("\n" + "="*80)
        print("🎉 ALL TESTS COMPLETED!")
        print("="*80)

        # Clean up
        cleanup_test_subscriptions(db, user.id)

        return 0

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
