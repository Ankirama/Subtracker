"""Fix demo subscriptions by linking them to the demo mailbox."""

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, Mailbox, Subscription

DEMO_EMAIL = "demo@subscriptionstracker.io"

db = SessionLocal()
try:
    # Get demo user
    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if not user:
        print(f"❌ Demo user not found: {DEMO_EMAIL}")
        exit(1)

    # Get demo mailbox
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.user_id == user.id, Mailbox.email_address == DEMO_EMAIL)
        .first()
    )

    if not mailbox:
        print(f"❌ Demo mailbox not found")
        exit(1)

    print(f"✓ Found demo mailbox: {mailbox.id}")

    # Update subscriptions without mailbox_id
    subscriptions = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.mailbox_id == None)
        .all()
    )

    print(f"Found {len(subscriptions)} subscriptions without mailbox")

    for sub in subscriptions:
        sub.mailbox_id = mailbox.id
        print(f"  Linking {sub.provider} to mailbox")

    db.commit()

    # Verify
    total_subs = db.query(Subscription).filter(Subscription.user_id == user.id).count()

    linked_subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.mailbox_id != None)
        .count()
    )

    print(f"\n✅ Success!")
    print(f"Total subscriptions: {total_subs}")
    print(f"Linked to mailbox: {linked_subs}")

finally:
    db.close()
