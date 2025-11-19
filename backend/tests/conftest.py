"""
Test configuration and fixtures for the subscription tracker backend.
"""
import os
import pytest
import json
from typing import Generator
from sqlalchemy import create_engine, event, TypeDecorator, CHAR, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID, JSONB as PostgreSQL_JSONB, ARRAY as PostgreSQL_ARRAY
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
import uuid

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.email_message import EmailMessage
from app.security.password import hash_password


# UUID type for SQLite compatibility
class GUID(TypeDecorator):
    """Platform-independent GUID type that uses PostgreSQL's UUID or CHAR(36) in other databases."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQL_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value


# JSONB type for SQLite compatibility
class JSON_SQLite(TypeDecorator):
    """Platform-independent JSON type that uses PostgreSQL's JSONB or TEXT in SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQL_JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'sqlite':
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'sqlite':
            return json.loads(value)
        return value


# ARRAY type for SQLite compatibility
class ARRAY_SQLite(TypeDecorator):
    """Platform-independent ARRAY type that uses PostgreSQL's ARRAY or TEXT in SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            # For PostgreSQL, we need to get the item type from the original ARRAY
            return dialect.type_descriptor(PostgreSQL_ARRAY(Text))
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'sqlite':
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'sqlite':
            return json.loads(value) if value else []
        return value


# Test database URL - use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Replace PostgreSQL-specific types with SQLite-compatible types
    @event.listens_for(Base.metadata, "column_reflect")
    def receive_column_reflect(inspector, table, column_info):
        if isinstance(column_info['type'], PostgreSQL_UUID):
            column_info['type'] = GUID()
        elif isinstance(column_info['type'], PostgreSQL_JSONB):
            column_info['type'] = JSON_SQLite()
        elif isinstance(column_info['type'], PostgreSQL_ARRAY):
            column_info['type'] = ARRAY_SQLite()

    # Override UUID, JSONB, and ARRAY columns in models for SQLite
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.sql.sqltypes import ARRAY as BaseARRAY
    for table in Base.metadata.tables.values():
        for column in table.columns:
            # Check type by class name to catch all variants
            type_name = column.type.__class__.__name__
            if isinstance(column.type, postgresql.UUID):
                column.type = GUID()
            elif isinstance(column.type, postgresql.JSONB):
                column.type = JSON_SQLite()
            elif isinstance(column.type, (postgresql.ARRAY, BaseARRAY)) or type_name == 'ARRAY':
                column.type = ARRAY_SQLite()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database session override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create a test user (verified by default for compatibility)."""
    password_hash, salt = hash_password("testpassword123")
    user = User(
        email="test@example.com",
        password_hash=password_hash,
        salt=salt,
        is_active=True,
        email_verified=True,  # Verified by default for existing tests
        settings={}
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_mailbox(db_session: Session, test_user: User) -> Mailbox:
    """Create a test mailbox."""
    mailbox = Mailbox(
        user_id=test_user.id,
        email_address="test@fastmail.com",
        provider_type="jmap",
        encrypted_credentials="test_encrypted_credentials",
        is_active=True
    )
    db_session.add(mailbox)
    db_session.commit()
    db_session.refresh(mailbox)
    return mailbox


@pytest.fixture(scope="function")
def test_subscription(db_session: Session, test_mailbox: Mailbox) -> Subscription:
    """Create a test subscription."""
    from datetime import datetime, timezone

    subscription = Subscription(
        user_id=test_mailbox.user_id,
        mailbox_id=test_mailbox.id,
        provider="Netflix",
        amount=15.99,
        currency="EUR",
        billing_cycle="monthly",
        category="streaming",
        is_active=True,
        is_confirmed=True,
        extraction_method="ai",
        confidence_score=0.95,
        first_detected_at=datetime.now(timezone.utc),
        last_confirmed_at=datetime.now(timezone.utc)
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)
    return subscription


@pytest.fixture(scope="function")
def test_email(db_session: Session, test_mailbox: Mailbox) -> EmailMessage:
    """Create a test email."""
    from datetime import datetime, timezone

    email = EmailMessage(
        mailbox_id=test_mailbox.id,
        message_id="test-message-id-001",
        subject="Your Netflix subscription",
        sender="netflix@netflix.com",
        recipient=test_mailbox.email_address,
        date=datetime.now(timezone.utc),
        body_text="Your subscription renews on December 5, 2025 for $15.99",
        is_subscription=True,
        classification_confidence=0.95
    )
    db_session.add(email)
    db_session.commit()
    db_session.refresh(email)
    return email


@pytest.fixture
def auth_headers(client: TestClient, test_user: User) -> dict:
    """Get authentication headers for API requests."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword123"
        }
    )
    assert response.status_code == 200
    token_data = response.json()
    return {"Authorization": f"Bearer {token_data['access_token']}"}


@pytest.fixture(scope="function")
def admin_user(db_session: Session) -> User:
    """Create an admin user (verified and admin)."""
    password_hash, salt = hash_password("adminpassword123")
    user = User(
        email="admin@example.com",
        password_hash=password_hash,
        salt=salt,
        is_active=True,
        is_admin=True,
        email_verified=True,
        settings={}
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(client: TestClient, admin_user: User) -> dict:
    """Get authentication headers for admin API requests."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": admin_user.email,
            "password": "adminpassword123"
        }
    )
    assert response.status_code == 200
    token_data = response.json()
    return {"Authorization": f"Bearer {token_data['access_token']}"}


# Mock data fixtures for testing
@pytest.fixture
def sample_email_dates():
    """Sample email dates for testing renewal calculation."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    return [
        now,
        now - timedelta(days=30),
        now - timedelta(days=60),
        now - timedelta(days=90)
    ]


@pytest.fixture
def sample_email_contents():
    """Sample email contents for testing pattern extraction."""
    return [
        "Your subscription renews on December 5, 2025 for $15.99",
        "Your next invoice will be on November 5, 2025",
        "Billing date: October 5, 2025",
        "Your subscription has been renewed"
    ]


@pytest.fixture
def sample_trial_metadata():
    """Sample trial detection metadata."""
    return {
        'trial_detected': True,
        'trial_keywords': ['free trial', 'trial period'],
        'detected_at': '2025-11-01T00:00:00Z'
    }
