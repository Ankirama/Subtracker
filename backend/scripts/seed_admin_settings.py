#!/usr/bin/env python3
"""
Seed script to populate admin_settings table with initial configuration values.

This script reads current .env values and creates admin_settings records for
admin-configurable settings. Run this once during setup or when adding new
configurable settings.

Usage:
    python -m scripts.seed_admin_settings
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.admin import AdminSetting
from app.config import settings
from app.utils.encryption import encryption_service
import uuid


def seed_admin_settings(db: Session, overwrite: bool = False):
    """
    Seed admin settings from current environment configuration.

    Args:
        db: Database session
        overwrite: If True, update existing settings. If False, skip existing ones.
    """
    # Define settings to seed with metadata
    settings_to_seed = [
        # SendGrid configuration
        {
            "key": "sendgrid.api_key",
            "value": settings.SENDGRID_API_KEY,
            "value_type": "string",
            "is_secret": True,
            "description": "SendGrid API key for sending transactional emails",
            "category": "email",
        },
        {
            "key": "sendgrid.from_email",
            "value": settings.SENDGRID_FROM_EMAIL,
            "value_type": "string",
            "is_secret": False,
            "description": "From email address for outgoing emails",
            "category": "email",
        },
        {
            "key": "sendgrid.from_name",
            "value": settings.SENDGRID_FROM_NAME,
            "value_type": "string",
            "is_secret": False,
            "description": "From name for outgoing emails",
            "category": "email",
        },
        # OpenAI configuration
        {
            "key": "openai.api_key",
            "value": settings.OPENAI_API_KEY,
            "value_type": "string",
            "is_secret": True,
            "description": "OpenAI API key for AI classification and extraction",
            "category": "ai",
        },
        {
            "key": "openai.assistant_id",
            "value": settings.OPENAI_ASSISTANT_ID,
            "value_type": "string",
            "is_secret": False,
            "description": "OpenAI Assistant ID (optional)",
            "category": "ai",
        },
        {
            "key": "openai.request_delay_seconds",
            "value": settings.OPENAI_REQUEST_DELAY_SECONDS,
            "value_type": "number",
            "is_secret": False,
            "description": "Delay between OpenAI API calls in seconds",
            "category": "ai",
        },
        {
            "key": "openai.max_requests_per_minute",
            "value": settings.OPENAI_MAX_REQUESTS_PER_MINUTE,
            "value_type": "number",
            "is_secret": False,
            "description": "Maximum OpenAI API requests per minute",
            "category": "ai",
        },
        # Email processing configuration
        {
            "key": "email.default_batch_size",
            "value": settings.DEFAULT_BATCH_SIZE,
            "value_type": "number",
            "is_secret": False,
            "description": "Default batch size for email processing",
            "category": "processing",
        },
        {
            "key": "email.confidence_auto_accept",
            "value": settings.DEFAULT_CONFIDENCE_AUTO_ACCEPT,
            "value_type": "number",
            "is_secret": False,
            "description": "Confidence threshold for auto-accepting subscriptions (%)",
            "category": "processing",
        },
        {
            "key": "email.confidence_review_min",
            "value": settings.DEFAULT_CONFIDENCE_REVIEW_MIN,
            "value_type": "number",
            "is_secret": False,
            "description": "Minimum confidence threshold for review queue (%)",
            "category": "processing",
        },
        {
            "key": "email.default_sync_period_days",
            "value": settings.DEFAULT_SYNC_PERIOD_DAYS,
            "value_type": "number",
            "is_secret": False,
            "description": "Default email sync period in days",
            "category": "processing",
        },
        # Frontend configuration
        {
            "key": "frontend.url",
            "value": settings.FRONTEND_URL,
            "value_type": "string",
            "is_secret": False,
            "description": "Frontend application URL",
            "category": "application",
        },
    ]

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for setting_data in settings_to_seed:
        key = setting_data["key"]

        # Check if setting already exists
        existing = db.query(AdminSetting).filter(AdminSetting.key == key).first()

        if existing and not overwrite:
            print(f"⏭️  Skipping existing setting: {key}")
            skipped_count += 1
            continue

        # Prepare value (encrypt if secret)
        value = setting_data["value"]
        if setting_data["is_secret"] and value:
            value = encryption_service.encrypt(value)

        if existing:
            # Update existing setting
            existing.value = value
            existing.value_type = setting_data["value_type"]
            existing.is_secret = setting_data["is_secret"]
            existing.description = setting_data["description"]
            existing.category = setting_data["category"]
            print(f"🔄 Updated setting: {key}")
            updated_count += 1
        else:
            # Create new setting
            new_setting = AdminSetting(
                id=uuid.uuid4(),
                key=key,
                value=value,
                value_type=setting_data["value_type"],
                is_secret=setting_data["is_secret"],
                description=setting_data["description"],
                category=setting_data["category"],
            )
            db.add(new_setting)
            print(f"✅ Created setting: {key}")
            created_count += 1

    db.commit()

    print("\n" + "=" * 60)
    print("🎉 Seeding Complete!")
    print(f"   Created: {created_count}")
    print(f"   Updated: {updated_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Total:   {created_count + updated_count + skipped_count}")
    print("=" * 60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed admin settings from environment")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing settings (default: skip existing)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🌱 Seeding Admin Settings")
    print("=" * 60)

    if args.overwrite:
        print("⚠️  Overwrite mode enabled - will update existing settings")
    else:
        print("ℹ️  Skip mode enabled - will only create new settings")

    print()

    # Create database session
    db = SessionLocal()

    try:
        seed_admin_settings(db, overwrite=args.overwrite)
    except Exception as e:
        print(f"\n❌ Error seeding settings: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
