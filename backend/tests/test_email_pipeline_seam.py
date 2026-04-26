"""Seam-demonstration tests for the email-sync interface (Phase 8a).

These tests prove the dependency-injection seam introduced by
`app/services/email_pipeline_protocol.py` works: callers can pass mock
implementations of the AI classifier, subscription extractor, and
reference-extractor factory directly into `_sync_mailbox_async` instead of
monkeypatching module attributes.

Scope: just enough to demonstrate the seam exists. Broader chartest
coverage of the inner pipeline lives in `test_email_sync.py`.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.email_providers.base import EmailMessage as ProviderEmailMessage
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.tasks.email_sync import _sync_mailbox_async


def _make_provider_email(
    *,
    message_id: str = "seam-test-msg-1",
    sender: str = "netflix@netflix.com",
    subject: str = "Your Netflix subscription",
    body: str = "Your subscription renews soon",
    recipient: str = "test@fastmail.com",
) -> ProviderEmailMessage:
    """Build a provider-side EmailMessage dataclass for seam tests."""
    return ProviderEmailMessage(
        id=message_id,
        subject=subject,
        sender=sender,
        sender_name=None,
        recipients=[recipient],
        date=datetime.now(timezone.utc),
        body_text=body,
        body_html=None,
        headers={"Message-ID": message_id},
        has_attachments=False,
        folder=None,
    )


def _patch_provider_layer(stack, mailbox: Mailbox, provider_emails):
    """Apply the minimum patch set needed to drive `_sync_mailbox_async`.

    Patches credential decryption and JMAPProvider so the function runs in
    a unit-test context. Does NOT patch the AI batch functions: the seam
    tests inject those via parameters.
    """
    decrypt_patch = stack.enter_context(
        patch("app.tasks.email_sync.orchestrator.decrypt_credentials")
    )
    decrypt_patch.return_value = {"username": "u", "password": "p"}

    async def fake_authenticate():
        return True

    async def fake_close():
        return None

    async def fake_fetch_messages(
        folder=None, since_date=None, limit=100, search_query=None, position=0
    ):
        if position == 0:
            return (provider_emails, False)
        return ([], False)

    def make_mock_provider(*args, **kwargs):
        provider = MagicMock()
        provider.authenticate = fake_authenticate
        provider.close = fake_close
        provider.fetch_messages = fake_fetch_messages
        return provider

    jmap_patch = stack.enter_context(
        patch("app.tasks.email_sync.orchestrator.JMAPProvider")
    )
    jmap_patch.side_effect = make_mock_provider


@pytest.fixture
def seam_state(db_session: Session, test_mailbox: Mailbox):
    """Bundle the DB session and mailbox for seam tests."""
    return {"db": db_session, "mailbox": test_mailbox}


def test_inject_classify_batch_calls_mock_instead_of_default(seam_state):
    """`classify_batch` parameter must override the module-level default.

    Drives the seam: the injected mock receives the email batch; the real
    `classify_emails_batch` (which would hit OpenAI) is never called.
    """
    from contextlib import ExitStack

    db = seam_state["db"]
    mailbox = seam_state["mailbox"]

    provider_email = _make_provider_email(
        message_id="seam-msg-classify",
        recipient=mailbox.email_address,
    )

    classify_mock = AsyncMock(
        return_value=[
            {
                "is_subscription": False,
                "category": None,
                "confidence": 0.0,
                "reasoning": "mock",
            }
        ]
    )
    extract_mock = AsyncMock(return_value=[None])
    ref_factory = MagicMock(return_value=MagicMock())

    with ExitStack() as stack:
        _patch_provider_layer(stack, mailbox, [provider_email])

        result = asyncio.run(
            _sync_mailbox_async(
                db,
                mailbox,
                force_full_sync=True,
                date_filter=None,
                sync_start_time=datetime.now(timezone.utc),
                history_entry=MagicMock(),
                classify_batch=classify_mock,
                extract_batch=extract_mock,
                ref_extractor_factory=ref_factory,
            )
        )

    assert result["success"] is True
    assert classify_mock.await_count == 1
    # The classifier returned is_subscription=False, so the extractor must
    # NOT be called (no subscription emails to extract).
    assert extract_mock.await_count == 0


def test_inject_extract_batch_calls_mock_when_emails_are_subscriptions(seam_state):
    """`extract_batch` parameter must be invoked for subscription emails.

    With the classifier flagging the email as a subscription, the injected
    extractor mock is awaited. Its return value drives the rest of the
    pipeline; the real extractor (which would hit OpenAI) stays inert.
    """
    from contextlib import ExitStack

    db = seam_state["db"]
    mailbox = seam_state["mailbox"]

    provider_email = _make_provider_email(
        message_id="seam-msg-extract",
        recipient=mailbox.email_address,
    )

    classify_mock = AsyncMock(
        return_value=[
            {
                "is_subscription": True,
                "category": "streaming",
                "confidence": 0.95,
                "reasoning": "mock subscription",
            }
        ]
    )
    extract_mock = AsyncMock(
        return_value=[
            {
                "provider": "Netflix",
                "amount": 15.99,
                "currency": "EUR",
                "billing_cycle": "monthly",
                "email_sender": "netflix@netflix.com",
                "category": "streaming",
                "is_subscription": True,
                "is_price_update": False,
                "extraction_metadata": {"service_references": {}},
            }
        ]
    )
    ref_factory = MagicMock(return_value=MagicMock())

    with ExitStack() as stack:
        _patch_provider_layer(stack, mailbox, [provider_email])
        # Patch update_subscription_statuses to stay inert (post-sync hook
        # in the public Celery task; not exercised by this direct call).
        stack.enter_context(
            patch(
                "app.tasks.email_sync.celery_tasks.update_subscription_statuses",
                return_value={"activated": 0, "deactivated": 0},
            )
        )

        result = asyncio.run(
            _sync_mailbox_async(
                db,
                mailbox,
                force_full_sync=True,
                date_filter=None,
                sync_start_time=datetime.now(timezone.utc),
                history_entry=MagicMock(),
                classify_batch=classify_mock,
                extract_batch=extract_mock,
                ref_extractor_factory=ref_factory,
            )
        )

    assert result["success"] is True
    assert classify_mock.await_count == 1
    assert extract_mock.await_count == 1
    # Subscription created from the injected extractor's payload.
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.mailbox_id == mailbox.id, Subscription.provider == "Netflix"
        )
        .first()
    )
    assert sub is not None
    assert float(sub.amount) == 15.99


def test_inject_ref_extractor_factory_drives_dedup_strategy(seam_state):
    """`ref_extractor_factory` parameter must feed `find_best_match`.

    Pre-seed two existing Netflix subscriptions with distinct service
    references. Inject a `ReferenceExtractorProtocol` whose
    `can_match_subscription` returns True only for the second one. The
    incoming extraction should be merged into that second subscription
    (its amount becomes 19.99), proving the injected factory drove the
    dedup decision.
    """
    from contextlib import ExitStack

    db = seam_state["db"]
    mailbox = seam_state["mailbox"]

    target_metadata = {"service_references": {"account_id": "TARGET"}}
    other_metadata = {"service_references": {"account_id": "OTHER"}}

    other_sub = Subscription(
        user_id=mailbox.user_id,
        mailbox_id=mailbox.id,
        provider="Netflix",
        amount=10.0,
        currency="EUR",
        billing_cycle="monthly",
        email_sender="netflix@netflix.com",
        custom_label="other",
        category="streaming",
        is_active=True,
        is_confirmed=True,
        extraction_method="ai",
        confidence_score=0.9,
        first_detected_at=datetime.now(timezone.utc),
        last_confirmed_at=datetime.now(timezone.utc),
        extraction_metadata=other_metadata,
    )
    target_sub = Subscription(
        user_id=mailbox.user_id,
        mailbox_id=mailbox.id,
        provider="Netflix",
        amount=15.99,
        currency="EUR",
        billing_cycle="monthly",
        email_sender="netflix@netflix.com",
        custom_label="target",
        category="streaming",
        is_active=True,
        is_confirmed=True,
        extraction_method="ai",
        confidence_score=0.9,
        first_detected_at=datetime.now(timezone.utc),
        last_confirmed_at=datetime.now(timezone.utc),
        extraction_metadata=target_metadata,
    )
    db.add(other_sub)
    db.add(target_sub)
    db.commit()
    db.refresh(target_sub)
    target_id = target_sub.id

    provider_email = _make_provider_email(
        message_id="seam-msg-refext",
        recipient=mailbox.email_address,
    )

    classify_mock = AsyncMock(
        return_value=[
            {
                "is_subscription": True,
                "category": "streaming",
                "confidence": 0.95,
                "reasoning": "mock subscription",
            }
        ]
    )
    extract_mock = AsyncMock(
        return_value=[
            {
                "provider": "Netflix",
                "amount": 19.99,
                "currency": "EUR",
                "billing_cycle": "monthly",
                "email_sender": "netflix@netflix.com",
                "category": "streaming",
                "is_subscription": True,
                "is_price_update": False,
                # Same key/value as `target_sub.extraction_metadata`, so a
                # ref-extractor that compares them deeply will match.
                "extraction_metadata": dict(target_metadata),
            }
        ]
    )

    fake_ref_extractor = MagicMock()

    def fake_can_match(references, existing_metadata):
        # Only `target_sub.extraction_metadata` carries account_id == "TARGET".
        existing_refs = (existing_metadata or {}).get("service_references") or {}
        return existing_refs.get("account_id") == "TARGET"

    fake_ref_extractor.can_match_subscription.side_effect = fake_can_match
    ref_factory = MagicMock(return_value=fake_ref_extractor)

    with ExitStack() as stack:
        _patch_provider_layer(stack, mailbox, [provider_email])
        stack.enter_context(
            patch(
                "app.tasks.email_sync.celery_tasks.update_subscription_statuses",
                return_value={"activated": 0, "deactivated": 0},
            )
        )

        result = asyncio.run(
            _sync_mailbox_async(
                db,
                mailbox,
                force_full_sync=True,
                date_filter=None,
                sync_start_time=datetime.now(timezone.utc),
                history_entry=MagicMock(),
                classify_batch=classify_mock,
                extract_batch=extract_mock,
                ref_extractor_factory=ref_factory,
            )
        )

    assert result["success"] is True
    # The injected factory must have been invoked at least once during
    # subscription dedup.
    assert ref_factory.call_count >= 1
    assert fake_ref_extractor.can_match_subscription.call_count >= 1

    db.expire_all()
    refreshed_target = (
        db.query(Subscription).filter(Subscription.id == target_id).first()
    )
    assert refreshed_target is not None
    # Dedup picked `target_sub` and updated its amount to 19.99 — proof the
    # injected ref-extractor steered the strategy.
    assert float(refreshed_target.amount) == 19.99
    # No new subscription was created (still only the original two).
    netflix_count = (
        db.query(Subscription)
        .filter(
            Subscription.mailbox_id == mailbox.id, Subscription.provider == "Netflix"
        )
        .count()
    )
    assert netflix_count == 2
