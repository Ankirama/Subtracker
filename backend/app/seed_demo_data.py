"""
Seed script to create a demo user with realistic sample data.

Usage:
    python -m app.seed_demo_data

Or from Docker:
    docker exec subscriptions_backend python -m app.seed_demo_data
"""

import sys
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, Mailbox, Subscription, Budget, NotificationPreference
from app.models.notification import NotificationType
from app.security import hash_password
import uuid

# Demo user credentials
DEMO_EMAIL = "demo@subscriptionstracker.io"
DEMO_PASSWORD = "demo123"  # Simple password for demo purposes


def create_demo_user(db: Session) -> User:
    """Create or get the demo user."""
    user = db.query(User).filter(User.email == DEMO_EMAIL).first()

    if user:
        print(f"✓ Demo user already exists: {DEMO_EMAIL}")
        return user

    # Hash password returns (hashed_password, salt) tuple
    hashed_pwd, salt = hash_password(DEMO_PASSWORD)

    user = User(
        id=uuid.uuid4(),
        email=DEMO_EMAIL,
        password_hash=hashed_pwd,
        salt=salt,
        is_active=True,
        is_admin=False,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"✓ Created demo user: {DEMO_EMAIL}")
    return user


def create_demo_mailbox(db: Session, user_id: uuid.UUID) -> Mailbox:
    """Create or get a demo mailbox."""
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.user_id == user_id, Mailbox.email_address == DEMO_EMAIL)
        .first()
    )

    if mailbox:
        print("✓ Demo mailbox already exists")
        return mailbox

    mailbox = Mailbox(
        id=uuid.uuid4(),
        user_id=user_id,
        provider_type="demo",
        email_address=DEMO_EMAIL,
        encrypted_credentials="{}",  # Empty credentials for demo
        is_active=False,  # Disabled for demo - no actual email access
    )
    db.add(mailbox)
    db.commit()
    db.refresh(mailbox)
    print("✓ Created demo mailbox")
    return mailbox


def create_subscriptions(
    db: Session, user_id: uuid.UUID, mailbox_id: uuid.UUID
) -> list:
    """Create sample subscriptions."""
    today = datetime.utcnow()

    subscriptions_data = [
        {
            "name": "Netflix",
            "provider_name": "Netflix",
            "amount": Decimal("15.49"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Entertainment",
            "status": "active",
            "next_billing_date": today + timedelta(days=12),
            "start_date": today - timedelta(days=365),
        },
        {
            "name": "Spotify Premium",
            "provider_name": "Spotify",
            "amount": Decimal("10.99"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Entertainment",
            "status": "active",
            "next_billing_date": today + timedelta(days=8),
            "start_date": today - timedelta(days=730),
        },
        {
            "name": "Disney+",
            "provider_name": "Disney",
            "amount": Decimal("10.99"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Entertainment",
            "status": "active",
            "next_billing_date": today + timedelta(days=20),
            "start_date": today - timedelta(days=180),
        },
        {
            "name": "Amazon Prime",
            "provider_name": "Amazon",
            "amount": Decimal("139.00"),
            "currency": "USD",
            "billing_cycle": "yearly",
            "category": "Entertainment",
            "status": "active",
            "next_billing_date": today + timedelta(days=90),
            "start_date": today - timedelta(days=275),
        },
        {
            "name": "YouTube Premium",
            "provider_name": "YouTube",
            "amount": Decimal("11.99"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Entertainment",
            "status": "pending_review",
            "next_billing_date": today + timedelta(days=5),
            "start_date": today - timedelta(days=90),
        },
        {
            "name": "GitHub Pro",
            "provider_name": "GitHub",
            "amount": Decimal("4.00"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Software & Tools",
            "status": "active",
            "next_billing_date": today + timedelta(days=15),
            "start_date": today - timedelta(days=540),
        },
        {
            "name": "Adobe Creative Cloud",
            "provider_name": "Adobe",
            "amount": Decimal("54.99"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Software & Tools",
            "status": "active",
            "next_billing_date": today + timedelta(days=25),
            "start_date": today - timedelta(days=400),
        },
        {
            "name": "Dropbox Plus",
            "provider_name": "Dropbox",
            "amount": Decimal("11.99"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Cloud Storage",
            "status": "active",
            "next_billing_date": today + timedelta(days=18),
            "start_date": today - timedelta(days=600),
        },
        {
            "name": "Planet Fitness",
            "provider_name": "Planet Fitness",
            "amount": Decimal("24.99"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Health & Fitness",
            "status": "active",
            "next_billing_date": today + timedelta(days=10),
            "start_date": today - timedelta(days=120),
        },
        {
            "name": "The New York Times",
            "provider_name": "NYT",
            "amount": Decimal("17.00"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "News & Media",
            "status": "active",
            "next_billing_date": today + timedelta(days=22),
            "start_date": today - timedelta(days=200),
        },
        {
            "name": "HelloFresh",
            "provider_name": "HelloFresh",
            "amount": Decimal("89.94"),
            "currency": "USD",
            "billing_cycle": "weekly",
            "category": "Food & Dining",
            "status": "cancelled",
            "start_date": today - timedelta(days=150),
            "end_date": today - timedelta(days=30),
        },
        {
            "name": "Notion Pro",
            "provider_name": "Notion",
            "amount": Decimal("8.00"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Productivity",
            "status": "active",
            "next_billing_date": today + timedelta(days=14),
            "start_date": today - timedelta(days=300),
        },
        {
            "name": "Headspace",
            "provider_name": "Headspace",
            "amount": Decimal("12.99"),
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "Health & Fitness",
            "status": "pending_review",
            "next_billing_date": today + timedelta(days=7),
            "start_date": today - timedelta(days=60),
        },
    ]

    created_subscriptions = []

    for sub_data in subscriptions_data:
        # Check if subscription already exists
        existing = (
            db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.provider == sub_data["provider_name"],
            )
            .first()
        )

        if existing:
            continue

        subscription = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            mailbox_id=mailbox_id,
            provider=sub_data["provider_name"],
            email_sender=f"no-reply@{sub_data['provider_name'].lower().replace(' ', '')}.com",
            amount=sub_data["amount"],
            currency=sub_data["currency"],
            billing_cycle=sub_data["billing_cycle"],
            category=sub_data["category"],
            next_billing_date=sub_data.get("next_billing_date"),
            is_active=sub_data["status"] == "active",
            cancellation_status=sub_data["status"],
            trial_status="none",
            is_confirmed=True,
            confidence_score=1.0,  # Demo data is manually created, so 100% confident
            extraction_method="manual",  # Demo data is manually created
        )
        db.add(subscription)
        created_subscriptions.append(subscription)

    db.commit()
    print(f"✓ Created {len(created_subscriptions)} subscriptions")
    return created_subscriptions


def create_budgets(db: Session, user_id: uuid.UUID):
    """Create sample budgets."""
    budgets_data = [
        {
            "name": "Entertainment Budget",
            "limit_amount": Decimal("50.00"),
            "currency": "USD",
            "period": "monthly",
            "category": "Entertainment",
        },
        {
            "name": "Software & Tools Budget",
            "limit_amount": Decimal("100.00"),
            "currency": "USD",
            "period": "monthly",
            "category": "Software & Tools",
        },
        {
            "name": "Overall Subscription Budget",
            "limit_amount": Decimal("200.00"),
            "currency": "USD",
            "period": "monthly",
            "category": None,
        },
    ]

    created_budgets = []

    for budget_data in budgets_data:
        # Check if budget already exists
        existing = (
            db.query(Budget)
            .filter(Budget.user_id == user_id, Budget.name == budget_data["name"])
            .first()
        )

        if existing:
            continue

        budget = Budget(
            id=uuid.uuid4(),
            user_id=user_id,
            name=budget_data["name"],
            limit_amount=budget_data["limit_amount"],
            currency=budget_data["currency"],
            period=budget_data["period"],
            category=budget_data["category"],
        )
        db.add(budget)
        created_budgets.append(budget)

    db.commit()
    print(f"✓ Created {len(created_budgets)} budgets")


def disable_notifications(db: Session, user_id: uuid.UUID):
    """Disable all notifications for the demo user to prevent accidental emails."""
    # Create notification preferences with all notifications disabled
    notification_types = [
        NotificationType.RENEWAL_REMINDER,
        NotificationType.TRIAL_ENDING,
        NotificationType.WEEKLY_SUMMARY,
        NotificationType.MONTHLY_SUMMARY,
        NotificationType.INACTIVE_SUBSCRIPTION,
        NotificationType.PRICE_CHANGE,
        NotificationType.BUDGET_ALERT,
        NotificationType.SYSTEM_ANNOUNCEMENT,
    ]

    created_prefs = []
    for notification_type in notification_types:
        # Check if preference already exists
        existing = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
            .first()
        )

        if existing:
            # Update to disable if it exists
            existing.enabled = False
            existing.email_enabled = False
            existing.in_app_enabled = False
            continue

        # Create new disabled preference
        pref = NotificationPreference(
            id=uuid.uuid4(),
            user_id=user_id,
            notification_type=notification_type,
            enabled=False,
            email_enabled=False,
            in_app_enabled=False,
        )
        db.add(pref)
        created_prefs.append(pref)

    db.commit()
    print("✓ Disabled all notifications for demo user (safety measure)")


def seed_demo_data():
    """Main function to seed demo data."""
    print("=" * 60)
    print("SEEDING DEMO DATA")
    print("=" * 60)

    db = SessionLocal()
    try:
        # Create demo user
        user = create_demo_user(db)

        # Create demo mailbox
        mailbox = create_demo_mailbox(db, user.id)

        # Create subscriptions
        create_subscriptions(db, user.id, mailbox.id)

        # Create budgets
        create_budgets(db, user.id)

        # Disable all notifications for safety
        disable_notifications(db, user.id)

        print("=" * 60)
        print("✅ DEMO DATA SEEDED SUCCESSFULLY!")
        print("=" * 60)
        print("Demo user credentials:")
        print(f"  Email: {DEMO_EMAIL}")
        print(f"  Password: {DEMO_PASSWORD}")
        print("=" * 60)
        print("⚠️  All notifications disabled for this demo account")

    except Exception as e:
        print(f"❌ Error seeding demo data: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
