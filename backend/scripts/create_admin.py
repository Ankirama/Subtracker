#!/usr/bin/env python3
"""
Create an admin user for Subscription Tracker.

Usage (inside the backend container):
    python -m scripts.create_admin --email admin@example.com --password yourpassword

Or from docker:
    docker compose -f docker-compose.prod.yml exec backend python -m scripts.create_admin \
        --email admin@example.com --password yourpassword
"""

import argparse
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.security.password import hash_password
import uuid
from datetime import datetime


def create_admin_user(email: str, password: str, display_name: str = None):
    """Create an admin user directly in the database."""

    # Get database URL from environment
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Create engine and session
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if user already exists
        result = session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if result:
            print(f"User with email '{email}' already exists.")
            # Make them admin directly (non-interactive for Docker)
            session.execute(
                text("UPDATE users SET is_admin = true WHERE email = :email"),
                {"email": email}
            )
            session.commit()
            print(f"User '{email}' is now an admin.")
            return

        # Hash the password using the app's security module
        password_hash, salt = hash_password(password)

        # Generate UUID
        user_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Insert the user with all required columns
        session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, salt, display_name, is_active, is_admin, email_verified, settings, backup_codes, created_at, updated_at)
                VALUES (:id, :email, :password_hash, :salt, :display_name, true, true, true, '{}', '[]', :created_at, :updated_at)
            """),
            {
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "salt": salt,
                "display_name": display_name,
                "created_at": now,
                "updated_at": now,
            }
        )
        session.commit()

        print(f"Admin user created successfully!")
        print(f"  Email: {email}")
        print(f"  Display Name: {display_name or '(not set)'}")
        print(f"  ID: {user_id}")
        print(f"\nYou can now log in at your Subscription Tracker instance.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: Failed to create admin user: {e}")
        sys.exit(1)
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create an admin user for Subscription Tracker"
    )
    parser.add_argument(
        "--email", "-e",
        required=True,
        help="Email address for the admin user"
    )
    parser.add_argument(
        "--password", "-p",
        required=True,
        help="Password for the admin user"
    )
    parser.add_argument(
        "--name", "-n",
        default=None,
        help="Display name for the admin user (optional)"
    )

    args = parser.parse_args()

    # Validate email format (basic check)
    if "@" not in args.email:
        print("ERROR: Invalid email format")
        sys.exit(1)

    # Validate password length
    if len(args.password) < 8:
        print("ERROR: Password must be at least 8 characters long")
        sys.exit(1)

    create_admin_user(args.email, args.password, args.name)


if __name__ == "__main__":
    main()
