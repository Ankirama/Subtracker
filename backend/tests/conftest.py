"""
Test configuration and fixtures for the subscription tracker backend.
"""

import pytest
import json
from typing import Generator
from sqlalchemy import create_engine, event, TypeDecorator, CHAR, Text
from sqlalchemy.dialects.postgresql import (
    UUID as PostgreSQL_UUID,
    JSONB as PostgreSQL_JSONB,
    ARRAY as PostgreSQL_ARRAY,
)
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
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQL_UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
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
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQL_JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "sqlite":
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "sqlite":
            return json.loads(value)
        return value


# ARRAY type for SQLite compatibility
class ARRAY_SQLite(TypeDecorator):
    """Platform-independent ARRAY type that uses PostgreSQL's ARRAY or TEXT in SQLite."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            # For PostgreSQL, we need to get the item type from the original ARRAY
            return dialect.type_descriptor(PostgreSQL_ARRAY(Text))
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "sqlite":
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "sqlite":
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
        if isinstance(column_info["type"], PostgreSQL_UUID):
            column_info["type"] = GUID()
        elif isinstance(column_info["type"], PostgreSQL_JSONB):
            column_info["type"] = JSON_SQLite()
        elif isinstance(column_info["type"], PostgreSQL_ARRAY):
            column_info["type"] = ARRAY_SQLite()

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
            elif (
                isinstance(column.type, (postgresql.ARRAY, BaseARRAY))
                or type_name == "ARRAY"
            ):
                column.type = ARRAY_SQLite()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
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
        settings={},
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
        is_active=True,
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
        last_confirmed_at=datetime.now(timezone.utc),
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
        classification_confidence=0.95,
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
        json={"email": test_user.email, "password": "testpassword123"},
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
        settings={},
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
        json={"email": admin_user.email, "password": "adminpassword123"},
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
        now - timedelta(days=90),
    ]


@pytest.fixture
def sample_email_contents():
    """Sample email contents for testing pattern extraction."""
    return [
        "Your subscription renews on December 5, 2025 for $15.99",
        "Your next invoice will be on November 5, 2025",
        "Billing date: October 5, 2025",
        "Your subscription has been renewed",
    ]


@pytest.fixture
def sample_trial_metadata():
    """Sample trial detection metadata."""
    return {
        "trial_detected": True,
        "trial_keywords": ["free trial", "trial period"],
        "detected_at": "2025-11-01T00:00:00Z",
    }


@pytest.fixture(scope="function")
def commit_rollback_counter(db_session: Session):
    """
    Wrap db_session.commit and db_session.rollback to count calls.

    Yields a counter object with .commits and .rollbacks integer attributes,
    plus a .reset() method. Used by chartests that assert transactional parity
    (e.g., "the inner pipeline must commit once per email and once per batch").

    The wrapping is reverted on teardown.
    """
    from types import SimpleNamespace

    counter = SimpleNamespace(commits=0, rollbacks=0)

    original_commit = db_session.commit
    original_rollback = db_session.rollback

    def counting_commit(*args, **kwargs):
        counter.commits += 1
        return original_commit(*args, **kwargs)

    def counting_rollback(*args, **kwargs):
        counter.rollbacks += 1
        return original_rollback(*args, **kwargs)

    def reset():
        counter.commits = 0
        counter.rollbacks = 0

    counter.reset = reset

    db_session.commit = counting_commit
    db_session.rollback = counting_rollback

    yield counter

    db_session.commit = original_commit
    db_session.rollback = original_rollback


def test_commit_rollback_counter_smoke(
    commit_rollback_counter, db_session: Session, test_user
):
    """Smoke test for the commit_rollback_counter fixture."""
    assert commit_rollback_counter.commits == 1  # test_user fixture committed
    assert commit_rollback_counter.rollbacks == 0

    db_session.commit()
    assert commit_rollback_counter.commits == 2

    db_session.rollback()
    assert commit_rollback_counter.rollbacks == 1

    commit_rollback_counter.reset()
    assert commit_rollback_counter.commits == 0
    assert commit_rollback_counter.rollbacks == 0


@pytest.fixture(scope="function")
def email_sync_harness(db_session: Session, test_user: User, test_mailbox: Mailbox):
    """
    Test harness driving the inner pipeline of `_sync_mailbox_async` via the
    public `sync_mailbox_emails` Celery task.

    Patches the module-level collaborators of `app.tasks.email_sync`:
      - `SessionLocal`            → returns the test `db_session`
      - `decrypt_credentials`      → returns a stub credentials dict
      - `JMAPProvider`             → returns a MagicMock provider whose
                                     `fetch_messages()` yields the queued
                                     provider-side EmailMessage dataclasses
      - `app.services.ai_classifier.classify_emails_batch`
                                  → returns a list of classification dicts
                                    aligned with input order
      - `app.services.subscription_extractor.extract_subscriptions_batch`
                                  → returns a list of extraction dicts
                                    aligned with input order
      - `app.services.reference_extractor.get_reference_extractor`
                                  → returns a MagicMock whose
                                    `can_match_subscription` defaults to False;
                                    tests can override via
                                    `state.mock_reference_extractor`.

    Critically does NOT patch `asyncio.run` — the inner coroutine actually
    executes and operates on the same SQLAlchemy session as the test.

    Adjustments from the plan's verbatim fixture (documented for maintainers):
      - The plan suggested patching `create_email_provider`, `AIClassifier`,
        `SubscriptionExtractor`, `ReferenceExtractor`. The actual code uses
        `JMAPProvider`/`GmailProvider` directly and module-level batch
        functions (`classify_emails_batch`, `extract_subscriptions_batch`),
        not classes. We patch what the code actually uses.
      - The provider's method is `fetch_messages` and returns a tuple
        `(emails: List[EmailMessage], has_more: bool)` — NOT an async
        generator. We mock it accordingly.
      - We add `decrypt_credentials` to the patch set because the test
        mailbox stores a placeholder string that real Fernet cannot decrypt.
      - We patch `update_subscription_statuses` to be a passthrough (it
        runs after the inner sync and queries subscriptions independently;
        the chartests do not assert on its output and SQLite tz quirks
        could cause flakiness).

    Usage:
        def test_X(email_sync_harness):
            h = email_sync_harness
            sub = h.add_existing_sub(provider="Netflix", amount=15.99)
            h.add_email(sender="netflix@netflix.com",
                        extraction={"provider": "Netflix", "amount": 16.99, ...})
            result = h.run_sync()
            assert result["success"] is True
            assert h.get_sub(provider="Netflix").amount == 16.99
    """
    from contextlib import ExitStack
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import patch, MagicMock
    from sqlalchemy import text

    from app.email_providers.base import EmailMessage as ProviderEmailMessage
    from app.models.email_message import EmailMessage as DBEmailMessage
    from app.models.subscription import Subscription
    from app.models.price_history import PriceHistory

    state = SimpleNamespace()
    state.db = db_session
    state.mailbox = test_mailbox
    state.queued_emails = (
        []
    )  # list of dicts: provider_email, classification, extraction

    # ---- Setup helpers ----

    def add_email(
        *,
        message_id=None,
        sender="netflix@netflix.com",
        sender_name=None,
        subject="Test",
        body="Test body",
        body_html=None,
        date=None,
        is_subscription=True,
        category="subscription",
        confidence=0.9,
        reasoning="",
        extraction=None,
    ):
        """Queue a provider-side EmailMessage dataclass and its mocked
        classification + extraction results. The DB row is created by the
        inner pipeline itself when it processes the provider's emails."""
        msg_id = message_id or f"test-msg-{len(state.queued_emails)}"
        provider_email = ProviderEmailMessage(
            id=msg_id,
            subject=subject,
            sender=sender,
            sender_name=sender_name,
            recipients=[state.mailbox.email_address],
            date=date or datetime.now(timezone.utc),
            body_text=body,
            body_html=body_html,
            headers={"Message-ID": msg_id},
            has_attachments=False,
            folder=None,
        )

        ext = (
            extraction
            if extraction is not None
            else {
                "provider": "Netflix",
                "amount": 15.99,
                "currency": "EUR",
                "billing_cycle": "monthly",
                "email_sender": sender,
                "category": "streaming",
                "is_subscription": True,
                "is_price_update": False,
                "extraction_metadata": {"service_references": {}},
            }
        )
        state.queued_emails.append(
            {
                "provider_email": provider_email,
                "classification": {
                    "is_subscription": is_subscription,
                    "category": category,
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                "extraction": ext,
            }
        )
        return provider_email

    def add_existing_sub(
        *,
        provider="Netflix",
        amount=15.99,
        billing_cycle="monthly",
        email_sender=None,
        custom_label="",
        **extra,
    ):
        sub = Subscription(
            user_id=state.mailbox.user_id,
            mailbox_id=state.mailbox.id,
            provider=provider,
            amount=amount,
            currency="EUR",
            billing_cycle=billing_cycle,
            email_sender=email_sender,
            custom_label=custom_label,
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
            **extra,
        )
        state.db.add(sub)
        state.db.commit()
        state.db.refresh(sub)
        return sub

    def link_email_to_sub(email_record, sub):
        """Insert a row in the subscription_emails association table.

        `email_record` may be either a DB EmailMessage row or a provider-side
        EmailMessage dataclass (we resolve the DB row by message_id in the
        latter case)."""
        if isinstance(email_record, ProviderEmailMessage):
            db_row = (
                state.db.query(DBEmailMessage)
                .filter(DBEmailMessage.message_id == email_record.id)
                .first()
            )
            if db_row is None:
                # Pre-create the DB row so it exists before sync runs
                db_row = DBEmailMessage(
                    mailbox_id=state.mailbox.id,
                    message_id=email_record.id,
                    subject=email_record.subject,
                    sender=email_record.sender,
                    recipient=state.mailbox.email_address,
                    date=email_record.date,
                    body_text=email_record.body_text,
                    is_subscription=True,
                    classification_confidence=0.9,
                )
                state.db.add(db_row)
                state.db.commit()
                state.db.refresh(db_row)
            email_id = db_row.id
        else:
            email_id = email_record.id
        state.db.execute(
            text(
                "INSERT INTO subscription_emails "
                "(subscription_id, email_id, extraction_role, extraction_data) "
                "VALUES (:sid, :eid, 'detection', '{}')"
            ),
            {"sid": str(sub.id), "eid": str(email_id)},
        )
        state.db.commit()

    # ---- Run ----

    def run_sync(force_full=False, date_filter=None):
        from app.tasks.email_sync import sync_mailbox_emails

        return sync_mailbox_emails.apply(
            kwargs={
                "mailbox_id": str(state.mailbox.id),
                "force_full_sync": force_full,
                "date_filter": date_filter,
            }
        ).get()

    # ---- Assertion helpers ----

    def count_subs(*, provider=None):
        q = state.db.query(Subscription).filter(
            Subscription.mailbox_id == state.mailbox.id
        )
        if provider:
            q = q.filter(Subscription.provider == provider)
        return q.count()

    def get_sub(*, provider, amount=None):
        q = state.db.query(Subscription).filter(
            Subscription.mailbox_id == state.mailbox.id,
            Subscription.provider == provider,
        )
        if amount is not None:
            q = q.filter(Subscription.amount == amount)
        return q.first()

    def all_subs(*, provider=None):
        q = state.db.query(Subscription).filter(
            Subscription.mailbox_id == state.mailbox.id
        )
        if provider:
            q = q.filter(Subscription.provider == provider)
        return q.order_by(Subscription.first_detected_at).all()

    def count_price_history(*, subscription_id=None, change_type=None):
        q = state.db.query(PriceHistory)
        if subscription_id:
            q = q.filter(PriceHistory.subscription_id == subscription_id)
        if change_type:
            q = q.filter(PriceHistory.change_type == change_type)
        return q.count()

    def email_links_for(sub_id):
        rows = state.db.execute(
            text(
                "SELECT email_id FROM subscription_emails "
                "WHERE subscription_id = :sid"
            ),
            {"sid": str(sub_id)},
        ).fetchall()
        return [r[0] for r in rows]

    state.add_email = add_email
    state.add_existing_sub = add_existing_sub
    state.link_email_to_sub = link_email_to_sub
    state.run_sync = run_sync
    state.count_subs = count_subs
    state.get_sub = get_sub
    state.all_subs = all_subs
    state.count_price_history = count_price_history
    state.email_links_for = email_links_for

    # ---- Patches ----

    stack = ExitStack()

    # Patch SessionLocal so DatabaseTask.db returns our test session.
    # Critically, we shadow `state.db.close` with a no-op for the duration of
    # the harness because DatabaseTask.after_return() calls `_db.close()` after
    # the celery task finishes. Without this, all ORM instances in the test
    # (including state.mailbox) become detached and assertions raise
    # DetachedInstanceError.
    original_close = state.db.close
    state.db.close = lambda: None
    stack.callback(setattr, state.db, "close", original_close)

    mock_session_local = stack.enter_context(patch("app.tasks.email_sync.SessionLocal"))
    mock_session_local.return_value = state.db

    # Patch credential decryption (the test mailbox has a placeholder string).
    mock_decrypt = stack.enter_context(
        patch("app.tasks.email_sync.decrypt_credentials")
    )
    mock_decrypt.return_value = {"username": "test", "password": "test"}

    # Patch JMAPProvider — the test_mailbox.provider_type is "jmap".
    # The provider needs async methods authenticate(), fetch_messages(), close().
    async def mock_authenticate():
        return True

    async def mock_close():
        return None

    async def mock_fetch_messages(
        folder=None, since_date=None, limit=100, search_query=None, position=0
    ):
        # Return all queued emails on first call; signal no more on subsequent.
        if position == 0:
            emails = [em["provider_email"] for em in state.queued_emails]
            return (emails, False)
        return ([], False)

    def make_mock_provider(*args, **kwargs):
        provider = MagicMock()
        provider.authenticate = mock_authenticate
        provider.close = mock_close
        provider.fetch_messages = mock_fetch_messages
        return provider

    mock_jmap = stack.enter_context(patch("app.tasks.email_sync.JMAPProvider"))
    mock_jmap.side_effect = make_mock_provider

    mock_gmail = stack.enter_context(patch("app.tasks.email_sync.GmailProvider"))
    mock_gmail.side_effect = make_mock_provider

    # Patch the AI batch functions where they live (the inner pipeline imports
    # them inside the function body via `from app.services.ai_classifier import
    # classify_emails_batch`, so we patch the source modules).
    async def mock_classify_emails_batch(emails, db=None, *args, **kwargs):
        results = []
        for em in emails:
            match = next(
                (q for q in state.queued_emails if q["provider_email"].id == em.id),
                None,
            )
            if match:
                results.append(match["classification"])
            else:
                results.append(
                    {
                        "is_subscription": False,
                        "category": None,
                        "confidence": 0.0,
                        "reasoning": "",
                    }
                )
        return results

    async def mock_extract_subscriptions_batch(emails, db=None, *args, **kwargs):
        results = []
        for em in emails:
            match = next(
                (q for q in state.queued_emails if q["provider_email"].id == em.id),
                None,
            )
            results.append(match["extraction"] if match else None)
        return results

    stack.enter_context(
        patch(
            "app.services.ai_classifier.classify_emails_batch",
            new=mock_classify_emails_batch,
        )
    )
    stack.enter_context(
        patch(
            "app.services.subscription_extractor.extract_subscriptions_batch",
            new=mock_extract_subscriptions_batch,
        )
    )

    # Patch get_reference_extractor — the inner pipeline imports it from
    # `app.services.reference_extractor` inside the function body.
    mock_reference_extractor = MagicMock()
    mock_reference_extractor.can_match_subscription.return_value = False
    stack.enter_context(
        patch(
            "app.services.reference_extractor.get_reference_extractor",
            return_value=mock_reference_extractor,
        )
    )
    state.mock_reference_extractor = mock_reference_extractor

    # Patch update_subscription_statuses — runs post-sync and queries
    # subscriptions; chartests do not assert on its output. Passthrough no-op
    # to avoid SQLite tz quirks.
    stack.enter_context(
        patch(
            "app.tasks.email_sync.update_subscription_statuses",
            return_value={"activated": 0, "deactivated": 0},
        )
    )

    yield state
    stack.close()


def test_email_sync_harness_smoke(email_sync_harness):
    """Smoke test: harness runs sync, queued email creates subscription."""
    h = email_sync_harness
    h.add_email(
        sender="netflix@netflix.com",
        extraction={
            "provider": "Netflix",
            "amount": 15.99,
            "currency": "EUR",
            "billing_cycle": "monthly",
            "email_sender": "netflix@netflix.com",
            "category": "streaming",
            "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        },
    )

    result = h.run_sync()

    assert result["success"] is True
    assert h.count_subs(provider="Netflix") == 1
