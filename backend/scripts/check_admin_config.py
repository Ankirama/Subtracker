#!/usr/bin/env python3
"""
Check admin configuration status and identify missing or incomplete settings.

This script compares the config_helper mappings with actual admin_settings records
to identify which settings are missing, incomplete, or need attention.

Usage:
    python -m scripts.check_admin_config
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.admin import AdminSetting
from app.models.sync_history import SyncHistory  # Import to resolve relationships
from app.config import settings
from typing import Dict, List, Any

# Define all expected settings from config_helper
EXPECTED_SETTINGS = {
    # SendGrid configuration
    'sendgrid.api_key': {
        'category': 'email',
        'value_type': 'string',
        'is_secret': True,
        'description': 'SendGrid API key for sending transactional emails',
        'required': True,
        'env_value': lambda: settings.SENDGRID_API_KEY
    },
    'sendgrid.from_email': {
        'category': 'email',
        'value_type': 'string',
        'is_secret': False,
        'description': 'From email address for outgoing emails',
        'required': True,
        'env_value': lambda: settings.SENDGRID_FROM_EMAIL
    },
    'sendgrid.from_name': {
        'category': 'email',
        'value_type': 'string',
        'is_secret': False,
        'description': 'From name for outgoing emails',
        'required': True,
        'env_value': lambda: settings.SENDGRID_FROM_NAME
    },

    # OpenAI configuration
    'openai.api_key': {
        'category': 'ai',
        'value_type': 'string',
        'is_secret': True,
        'description': 'OpenAI API key for AI classification and extraction',
        'required': True,
        'env_value': lambda: settings.OPENAI_API_KEY
    },
    'openai.assistant_id': {
        'category': 'ai',
        'value_type': 'string',
        'is_secret': False,
        'description': 'OpenAI Assistant ID (optional)',
        'required': False,
        'env_value': lambda: settings.OPENAI_ASSISTANT_ID
    },
    'openai.request_delay_seconds': {
        'category': 'ai',
        'value_type': 'number',
        'is_secret': False,
        'description': 'Delay between OpenAI API calls in seconds',
        'required': True,
        'env_value': lambda: settings.OPENAI_REQUEST_DELAY_SECONDS
    },
    'openai.max_requests_per_minute': {
        'category': 'ai',
        'value_type': 'number',
        'is_secret': False,
        'description': 'Maximum OpenAI API requests per minute',
        'required': True,
        'env_value': lambda: settings.OPENAI_MAX_REQUESTS_PER_MINUTE
    },

    # Email processing configuration
    'email.default_batch_size': {
        'category': 'processing',
        'value_type': 'number',
        'is_secret': False,
        'description': 'Default batch size for email processing',
        'required': True,
        'env_value': lambda: settings.DEFAULT_BATCH_SIZE
    },
    'email.confidence_auto_accept': {
        'category': 'processing',
        'value_type': 'number',
        'is_secret': False,
        'description': 'Confidence threshold for auto-accepting subscriptions (%)',
        'required': True,
        'env_value': lambda: settings.DEFAULT_CONFIDENCE_AUTO_ACCEPT
    },
    'email.confidence_review_min': {
        'category': 'processing',
        'value_type': 'number',
        'is_secret': False,
        'description': 'Minimum confidence threshold for review queue (%)',
        'required': True,
        'env_value': lambda: settings.DEFAULT_CONFIDENCE_REVIEW_MIN
    },
    'email.default_sync_period_days': {
        'category': 'processing',
        'value_type': 'number',
        'is_secret': False,
        'description': 'Default email sync period in days',
        'required': True,
        'env_value': lambda: settings.DEFAULT_SYNC_PERIOD_DAYS
    },

    # Frontend configuration
    'frontend.url': {
        'category': 'application',
        'value_type': 'string',
        'is_secret': False,
        'description': 'Frontend application URL',
        'required': True,
        'env_value': lambda: settings.FRONTEND_URL
    },
}


def check_config_status(db: Session) -> Dict[str, Any]:
    """
    Check configuration status and identify issues.

    Returns:
        Dict with status information including missing, incomplete, and valid settings.
    """
    # Get all existing admin settings
    existing_settings = {s.key: s for s in db.query(AdminSetting).all()}

    missing = []
    incomplete = []
    valid = []
    extra = []

    # Check expected settings
    for key, expected in EXPECTED_SETTINGS.items():
        if key not in existing_settings:
            missing.append({
                'key': key,
                'category': expected['category'],
                'required': expected['required'],
                'env_value': expected['env_value'](),
                'description': expected['description']
            })
        else:
            setting = existing_settings[key]
            issues = []

            # Check if value is missing or empty for required settings
            if expected['required'] and not setting.value:
                issues.append('missing_value')

            # Check if secret settings have placeholder values
            if expected['is_secret'] and setting.value:
                value_str = str(setting.value).strip('"')
                if value_str.startswith('your_') or value_str.startswith('sk-your'):
                    issues.append('placeholder_value')

            # Check type mismatch
            if setting.value_type != expected['value_type']:
                issues.append(f"type_mismatch (expected {expected['value_type']}, got {setting.value_type})")

            if issues:
                incomplete.append({
                    'key': key,
                    'category': expected['category'],
                    'issues': issues,
                    'current_value': '***' if expected['is_secret'] else setting.value,
                    'env_value': expected['env_value']()
                })
            else:
                valid.append({
                    'key': key,
                    'category': expected['category']
                })

    # Check for extra settings not in expected list
    for key in existing_settings:
        if key not in EXPECTED_SETTINGS:
            extra.append({
                'key': key,
                'category': existing_settings[key].category,
                'value_type': existing_settings[key].value_type
            })

    return {
        'missing': missing,
        'incomplete': incomplete,
        'valid': valid,
        'extra': extra,
        'total_expected': len(EXPECTED_SETTINGS),
        'total_found': len(existing_settings)
    }


def print_status(status: Dict[str, Any]):
    """Print configuration status in a readable format."""
    print("\n" + "="*70)
    print("📊 ADMIN CONFIGURATION STATUS")
    print("="*70)

    print(f"\n📈 Overview:")
    print(f"   Total Expected Settings: {status['total_expected']}")
    print(f"   Total Found in Database: {status['total_found']}")
    print(f"   ✅ Valid:     {len(status['valid'])}")
    print(f"   ⚠️  Incomplete: {len(status['incomplete'])}")
    print(f"   ❌ Missing:    {len(status['missing'])}")
    print(f"   ℹ️  Extra:      {len(status['extra'])}")

    # Missing settings
    if status['missing']:
        print("\n" + "="*70)
        print("❌ MISSING SETTINGS")
        print("="*70)
        for item in status['missing']:
            req_marker = "🔴 REQUIRED" if item['required'] else "🟡 OPTIONAL"
            print(f"\n{req_marker} {item['key']}")
            print(f"   Category:    {item['category']}")
            print(f"   Description: {item['description']}")
            env_display = '***' if 'api_key' in item['key'] else str(item['env_value'])
            print(f"   Env Value:   {env_display}")

    # Incomplete settings
    if status['incomplete']:
        print("\n" + "="*70)
        print("⚠️  INCOMPLETE SETTINGS")
        print("="*70)
        for item in status['incomplete']:
            print(f"\n⚠️  {item['key']}")
            print(f"   Category: {item['category']}")
            print(f"   Issues:   {', '.join(item['issues'])}")
            print(f"   Current:  {item['current_value']}")
            env_display = '***' if 'api_key' in item['key'] else str(item['env_value'])
            print(f"   Env Value: {env_display}")

    # Valid settings
    if status['valid']:
        print("\n" + "="*70)
        print("✅ VALID SETTINGS")
        print("="*70)
        by_category = {}
        for item in status['valid']:
            category = item['category']
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(item['key'])

        for category, keys in sorted(by_category.items()):
            print(f"\n📁 {category.upper()}")
            for key in keys:
                print(f"   ✅ {key}")

    # Extra settings
    if status['extra']:
        print("\n" + "="*70)
        print("ℹ️  EXTRA SETTINGS (not in config_helper)")
        print("="*70)
        for item in status['extra']:
            print(f"   ℹ️  {item['key']} ({item['category']}, {item['value_type']})")

    # Recommendations
    print("\n" + "="*70)
    print("💡 RECOMMENDATIONS")
    print("="*70)

    if status['missing']:
        print("\n🔧 To fix missing settings:")
        print("   Run: python -m scripts.seed_admin_settings")

    if status['incomplete']:
        print("\n🔧 To fix incomplete settings:")
        print("   1. Update via Admin Panel API: PUT /admin/config/{key}")
        print("   2. Or re-run seed with --overwrite: python -m scripts.seed_admin_settings --overwrite")

    if not status['missing'] and not status['incomplete']:
        print("\n✨ All settings are properly configured!")
        print("   Admin panel is ready to use.")

    print("\n" + "="*70 + "\n")


def main():
    """Main entry point."""
    print("\n🔍 Checking admin configuration status...")

    db = SessionLocal()
    try:
        status = check_config_status(db)
        print_status(status)

        # Return exit code based on status
        if status['missing'] or status['incomplete']:
            sys.exit(1)
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error checking configuration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        db.close()


if __name__ == "__main__":
    main()
