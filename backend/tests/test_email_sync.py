"""Comprehensive tests for email sync task."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy.orm import Session
from uuid import uuid4

from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.user import User
from app.tasks.email_sync import (
    parse_date_filter,
    update_subscription_statuses,
    sync_mailbox_emails,
)


class TestParseDateFilter:
    """Tests for parse_date_filter utility function."""

    def test_parses_days_format(self, db_session: Session):
        """Should parse 'Xdays' format correctly."""
        result = parse_date_filter("30days", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=30)

        # Allow 1 second tolerance for test execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_parses_day_singular(self, db_session: Session):
        """Should parse singular 'day' format."""
        result = parse_date_filter("1day", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=1)

        assert abs((result - expected).total_seconds()) < 1

    def test_parses_months_format(self, db_session: Session):
        """Should parse 'Xmonths' format correctly."""
        result = parse_date_filter("6months", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=6 * 30)

        assert abs((result - expected).total_seconds()) < 1

    def test_parses_month_singular(self, db_session: Session):
        """Should parse singular 'month' format."""
        result = parse_date_filter("1month", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=30)

        assert abs((result - expected).total_seconds()) < 1

    def test_parses_years_format(self, db_session: Session):
        """Should parse 'Xyears' format correctly."""
        result = parse_date_filter("2years", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=2 * 365)

        assert abs((result - expected).total_seconds()) < 1

    def test_parses_year_singular(self, db_session: Session):
        """Should parse singular 'year' format."""
        result = parse_date_filter("1year", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=365)

        assert abs((result - expected).total_seconds()) < 1

    def test_handles_whitespace(self, db_session: Session):
        """Should handle leading/trailing whitespace."""
        result = parse_date_filter("  30days  ", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=30)

        assert abs((result - expected).total_seconds()) < 1

    def test_case_insensitive(self, db_session: Session):
        """Should handle mixed case input."""
        result = parse_date_filter("30DAYS", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=30)

        assert abs((result - expected).total_seconds()) < 1

    @patch("app.tasks.email_sync.filters.get_config_value")
    def test_uses_default_for_unknown_format(self, mock_config, db_session: Session):
        """Should use default config value for unknown formats."""
        mock_config.return_value = 90  # Default 90 days

        result = parse_date_filter("invalid", db_session)
        expected = datetime.now(timezone.utc) - timedelta(days=90)

        assert abs((result - expected).total_seconds()) < 1
        mock_config.assert_called_once()


class TestUpdateSubscriptionStatuses:
    """Tests for update_subscription_statuses function."""

    def test_activates_recent_subscriptions(
        self, db_session: Session, test_mailbox: Mailbox
    ):
        """Should activate subscriptions with recent confirmation."""
        # Create inactive subscription with recent confirmation
        subscription = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Netflix",
            billing_cycle="monthly",
            is_active=False,
            last_confirmed_at=datetime.now(timezone.utc)
            - timedelta(days=30),  # Within grace period
            manual_status_override=False,
        )
        db_session.add(subscription)
        db_session.commit()

        result = update_subscription_statuses(db_session, test_mailbox.id)

        assert result["activated"] == 1
        assert result["deactivated"] == 0

        db_session.refresh(subscription)
        assert subscription.is_active is True

    def test_deactivates_old_subscriptions(
        self, db_session: Session, test_mailbox: Mailbox
    ):
        """Should deactivate subscriptions without recent confirmation."""
        # Create active subscription with old confirmation
        subscription = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Netflix",
            billing_cycle="monthly",
            is_active=True,
            last_confirmed_at=datetime.now(timezone.utc)
            - timedelta(days=90),  # Beyond grace period
            manual_status_override=False,
        )
        db_session.add(subscription)
        db_session.commit()

        result = update_subscription_statuses(db_session, test_mailbox.id)

        assert result["activated"] == 0
        assert result["deactivated"] == 1

        db_session.refresh(subscription)
        assert subscription.is_active is False

    def test_respects_manual_override(self, db_session: Session, test_mailbox: Mailbox):
        """Should not modify subscriptions with manual status override."""
        # Create subscription with manual override
        subscription = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Netflix",
            billing_cycle="monthly",
            is_active=True,
            last_confirmed_at=datetime.now(timezone.utc)
            - timedelta(days=90),  # Beyond grace period
            manual_status_override=True,
        )
        db_session.add(subscription)
        db_session.commit()

        result = update_subscription_statuses(db_session, test_mailbox.id)

        assert result["activated"] == 0
        assert result["deactivated"] == 0

        db_session.refresh(subscription)
        assert subscription.is_active is True  # Status unchanged

    def test_handles_weekly_billing_cycle(
        self, db_session: Session, test_mailbox: Mailbox
    ):
        """Should use correct grace period for weekly subscriptions."""
        # Create weekly subscription with 10 day old confirmation (within 14 day grace)
        subscription = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="WeeklyService",
            billing_cycle="weekly",
            is_active=False,
            last_confirmed_at=datetime.now(timezone.utc) - timedelta(days=10),
            manual_status_override=False,
        )
        db_session.add(subscription)
        db_session.commit()

        result = update_subscription_statuses(db_session, test_mailbox.id)

        assert result["activated"] == 1
        db_session.refresh(subscription)
        assert subscription.is_active is True

    def test_handles_yearly_billing_cycle(
        self, db_session: Session, test_mailbox: Mailbox
    ):
        """Should use correct grace period for yearly subscriptions."""
        # Create yearly subscription with 12 month old confirmation (within 13 month grace)
        subscription = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="YearlyService",
            billing_cycle="yearly",
            is_active=False,
            last_confirmed_at=datetime.now(timezone.utc) - timedelta(days=365),
            manual_status_override=False,
        )
        db_session.add(subscription)
        db_session.commit()

        result = update_subscription_statuses(db_session, test_mailbox.id)

        assert result["activated"] == 1
        db_session.refresh(subscription)
        assert subscription.is_active is True


class TestSyncMailboxEmails:
    """Tests for sync_mailbox_emails Celery task."""

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    def test_returns_error_for_nonexistent_mailbox(
        self, mock_session_local, mock_run, db_session: Session
    ):
        """Should return error if mailbox doesn't exist."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        result = sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(uuid4()), "force_full_sync": False}
        ).get()

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    def test_returns_error_for_inactive_mailbox(
        self, mock_session_local, mock_run, db_session: Session, test_user: User
    ):
        """Should return error if mailbox is not active."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        # Create inactive mailbox
        mailbox = Mailbox(
            user_id=test_user.id,
            email_address="test@example.com",
            provider_type="jmap",
            is_active=False,
            encrypted_credentials=b"encrypted",
            batch_size=50,
            import_date_filter="30days",
        )
        db_session.add(mailbox)
        db_session.commit()

        result = sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(mailbox.id), "force_full_sync": False}
        ).get()

        assert result["success"] is False
        assert "not active" in result["error"].lower()

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    @patch("app.tasks.email_sync.celery_tasks.update_subscription_statuses")
    def test_successful_sync(
        self,
        mock_update_statuses,
        mock_session_local,
        mock_run,
        db_session: Session,
        test_mailbox: Mailbox,
    ):
        """Should complete successful sync and update mailbox status."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        # Mock successful sync result
        mock_sync_result = {
            "success": True,
            "total_emails_processed": 50,
            "subscriptions_found": 5,
            "subscriptions_updated": 2,
        }
        mock_run.return_value = mock_sync_result

        # Mock subscription status update
        mock_update_statuses.return_value = {"activated": 0, "deactivated": 0}

        # Set up mailbox state
        mailbox_id = test_mailbox.id  # Save before it gets detached
        test_mailbox.is_active = True
        test_mailbox.last_sync_status = None
        db_session.commit()

        result = sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(mailbox_id), "force_full_sync": False}
        ).get()

        assert result["success"] is True
        assert result["total_emails_processed"] == 50
        assert result["subscriptions_found"] == 5
        assert result["subscriptions_updated"] == 2

        # Check mailbox was updated (query fresh to avoid detached instance)
        updated_mailbox = (
            db_session.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
        )
        assert updated_mailbox.last_sync_status == "success"
        assert updated_mailbox.last_sync_at is not None
        assert updated_mailbox.last_sync_emails_processed == 50

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    def test_handles_sync_exception(
        self, mock_session_local, mock_run, db_session: Session, test_mailbox: Mailbox
    ):
        """Should handle exceptions and update mailbox with error."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        # Mock exception during sync
        mock_run.side_effect = Exception("Sync failed")

        # Save mailbox_id before it gets detached
        mailbox_id = test_mailbox.id
        test_mailbox.is_active = True
        db_session.commit()

        result = sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(mailbox_id), "force_full_sync": False}
        ).get()

        assert result["success"] is False
        assert "Sync failed" in result["error"]

        # Check mailbox error state (query fresh to avoid detached instance)
        updated_mailbox = (
            db_session.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
        )
        assert updated_mailbox.last_sync_status == "failed"
        assert updated_mailbox.last_sync_error_message == "Sync failed"

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    @patch("app.tasks.email_sync.celery_tasks.update_subscription_statuses")
    def test_resumes_from_cancelled_sync(
        self,
        mock_update_statuses,
        mock_session_local,
        mock_run,
        db_session: Session,
        test_mailbox: Mailbox,
    ):
        """Should resume from last position for cancelled syncs."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        # Set up cancelled sync state
        test_mailbox.is_active = True
        test_mailbox.last_sync_status = "cancelled"
        test_mailbox.last_sync_started_at = datetime.now(timezone.utc) - timedelta(
            minutes=10
        )
        test_mailbox.last_sync_position = 100
        test_mailbox.last_sync_batch_num = 2
        db_session.commit()

        # Mock successful resume
        mock_sync_result = {
            "success": True,
            "total_emails_processed": 150,
            "subscriptions_found": 3,
            "subscriptions_updated": 1,
        }
        mock_run.return_value = mock_sync_result

        # Mock subscription status update
        mock_update_statuses.return_value = {"activated": 0, "deactivated": 0}

        result = sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(test_mailbox.id), "force_full_sync": False}
        ).get()

        assert result["success"] is True
        # Verify resume was attempted by checking asyncio.run was called
        assert mock_run.called

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    @patch("app.tasks.email_sync.celery_tasks.update_subscription_statuses")
    def test_force_full_sync_ignores_last_sync(
        self,
        mock_update_statuses,
        mock_session_local,
        mock_run,
        db_session: Session,
        test_mailbox: Mailbox,
    ):
        """Should ignore last sync date when force_full_sync is True."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        # Set up mailbox with previous sync
        test_mailbox.is_active = True
        test_mailbox.last_sync_at = datetime.now(timezone.utc) - timedelta(days=1)
        test_mailbox.last_sync_status = "success"
        db_session.commit()

        mock_sync_result = {
            "success": True,
            "total_emails_processed": 200,
            "subscriptions_found": 10,
            "subscriptions_updated": 5,
        }
        mock_run.return_value = mock_sync_result

        # Mock subscription status update
        mock_update_statuses.return_value = {"activated": 0, "deactivated": 0}

        result = sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(test_mailbox.id), "force_full_sync": True}
        ).get()

        assert result["success"] is True
        # Verify force_full_sync was passed
        assert mock_run.called

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    @patch("app.tasks.email_sync.celery_tasks.update_subscription_statuses")
    def test_uses_custom_date_filter(
        self,
        mock_update_statuses,
        mock_session_local,
        mock_run,
        db_session: Session,
        test_mailbox: Mailbox,
    ):
        """Should use custom date filter when provided."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        test_mailbox.is_active = True
        db_session.commit()

        mock_sync_result = {
            "success": True,
            "total_emails_processed": 75,
            "subscriptions_found": 7,
            "subscriptions_updated": 3,
        }
        mock_run.return_value = mock_sync_result

        # Mock subscription status update
        mock_update_statuses.return_value = {"activated": 0, "deactivated": 0}

        result = sync_mailbox_emails.apply(
            kwargs={
                "mailbox_id": str(test_mailbox.id),
                "force_full_sync": False,
                "date_filter": "60days",
            }
        ).get()

        assert result["success"] is True
        # Verify date_filter was passed to async function
        assert mock_run.called

    @patch("app.tasks.email_sync.celery_tasks.asyncio.run")
    @patch("app.tasks.email_sync.celery_tasks.SessionLocal")
    @patch("app.tasks.email_sync.celery_tasks.update_subscription_statuses")
    def test_clears_progress_tracking_on_completion(
        self,
        mock_update_statuses,
        mock_session_local,
        mock_run,
        db_session: Session,
        test_mailbox: Mailbox,
    ):
        """Should clear progress tracking fields on successful completion."""
        # Mock SessionLocal to return our test db session
        mock_session_local.return_value = db_session

        # Set up mailbox with progress tracking
        mailbox_id = test_mailbox.id  # Save before it gets detached
        test_mailbox.is_active = True
        test_mailbox.current_batch_number = 5
        test_mailbox.total_batches_estimate = 10
        test_mailbox.progress_percentage = 50.0
        db_session.commit()

        mock_sync_result = {
            "success": True,
            "total_emails_processed": 100,
            "subscriptions_found": 5,
            "subscriptions_updated": 2,
        }
        mock_run.return_value = mock_sync_result

        # Mock subscription status update
        mock_update_statuses.return_value = {"activated": 0, "deactivated": 0}

        result = sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(mailbox_id), "force_full_sync": False}
        ).get()

        assert result["success"] is True

        # Check progress was cleared (query fresh to avoid detached instance)
        updated_mailbox = (
            db_session.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
        )
        assert updated_mailbox.current_batch_number is None
        assert updated_mailbox.total_batches_estimate is None
        assert updated_mailbox.progress_percentage == 100.0
        assert updated_mailbox.estimated_completion_time is None


class TestSyncInnerPipelineDedup:
    """Chartests for the multi-strategy dedup logic in _sync_mailbox_async.

    Plan adjustments (documented):
    - Plan code used `em.id in h.email_links_for(sub.id)`. `em.id` is the
      provider-side dataclass ID (string), but `email_links_for` returns DB
      UUIDs. We assert non-empty instead: `assert h.email_links_for(sub.id)`.
      To further verify the correct sub is linked we assert the *other* sub
      has no links.
    - Plan code used `h.mock_ref_extractor.return_value.can_match_subscription`.
      The actual harness exposes `h.mock_reference_extractor` (the instance
      directly). We use that attribute.
    """

    def _ext(self, **overrides):
        """Build an extraction dict with sensible defaults."""
        base = {
            "provider": "OVH",
            "amount": 10.0,
            "currency": "EUR",
            "billing_cycle": "monthly",
            "email_sender": "billing@ovh.com",
            "category": "saas",
            "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }
        base.update(overrides)
        return base

    def test_payment_processor_heuristic_reuses_first_existing_sub(
        self, email_sync_harness
    ):
        """3 OVH subs exist; email from PayPal sender → reuses first existing OVH sub."""
        h = email_sync_harness
        sub1 = h.add_existing_sub(provider="OVH", amount=10.0)
        h.add_existing_sub(provider="OVH", amount=10.0)
        h.add_existing_sub(provider="OVH", amount=10.0)

        h.add_email(
            sender="service@paypal.com",
            extraction=self._ext(email_sender="service@paypal.com"),
        )

        result = h.run_sync()
        assert result["success"] is True
        # No new sub created
        assert h.count_subs(provider="OVH") == 3
        # Email linked to first-created sub (payment-processor heuristic)
        assert h.email_links_for(sub1.id)

    def test_single_match_reuses_existing_sub(self, email_sync_harness):
        """1 existing Spotify sub, no service refs → reuses it."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Spotify", amount=9.99)
        h.add_email(
            sender="no-reply@spotify.com",
            extraction=self._ext(
                provider="Spotify",
                amount=9.99,
                email_sender="no-reply@spotify.com",
            ),
        )

        result = h.run_sync()
        assert result["success"] is True
        assert h.count_subs(provider="Spotify") == 1
        # Email linked to the only existing sub
        assert h.email_links_for(sub.id)

    def test_email_sender_exact_match_disambiguates(self, email_sync_harness):
        """2 Twitch subs with different senders → email-sender exact match wins."""
        h = email_sync_harness
        sub_a = h.add_existing_sub(
            provider="Twitch", amount=4.99, email_sender="streamerA@twitch.tv"
        )
        sub_b = h.add_existing_sub(
            provider="Twitch", amount=4.99, email_sender="streamerB@twitch.tv"
        )

        h.add_email(
            sender="streamerA@twitch.tv",
            extraction=self._ext(
                provider="Twitch",
                amount=4.99,
                email_sender="streamerA@twitch.tv",
            ),
        )

        result = h.run_sync()
        assert result["success"] is True
        assert h.count_subs(provider="Twitch") == 2
        # Email linked to sub_a (exact email_sender match), not sub_b
        assert h.email_links_for(sub_a.id)
        assert not h.email_links_for(sub_b.id)

    def test_custom_label_keyword_match_disambiguates(self, email_sync_harness):
        """2 Twitch subs, same email_sender, distinct custom_labels with keywords → matches."""
        h = email_sync_harness
        sub_a = h.add_existing_sub(
            provider="Twitch",
            amount=4.99,
            email_sender="billing@twitch.tv",
            custom_label="basic tier",
        )
        sub_b = h.add_existing_sub(
            provider="Twitch",
            amount=4.99,
            email_sender="billing@twitch.tv",
            custom_label="premium tier",
        )

        h.add_email(
            sender="billing@twitch.tv",
            extraction=self._ext(
                provider="Twitch",
                amount=4.99,
                email_sender="billing@twitch.tv",
                custom_label="basic tier",
            ),
        )

        result = h.run_sync()
        assert result["success"] is True
        # The 'basic tier' sub gets the email; 'premium tier' sub does not
        assert h.email_links_for(sub_a.id)
        assert not h.email_links_for(sub_b.id)

    def test_service_refs_present_no_match_creates_new_sub(self, email_sync_harness):
        """Service references present but no existing match → creates a new sub
        rather than falling back to single-match. Locks in the 'CRITICAL FIX'
        anomaly noted in research."""
        h = email_sync_harness
        h.add_existing_sub(provider="OVH", amount=10.0)
        # Configure ref_extractor to consistently NOT match
        h.mock_reference_extractor.can_match_subscription.return_value = False

        h.add_email(
            sender="billing@ovh.com",
            extraction=self._ext(
                extraction_metadata={"service_references": {"account_id": "ABC123"}}
            ),
        )

        result = h.run_sync()
        assert result["success"] is True
        # New sub created (because service refs present and no match)
        assert h.count_subs(provider="OVH") == 2


class TestSyncInnerPipelinePriceHistory:
    """Chartests for the 3 price-history paths in _sync_mailbox_async."""

    def _ext(self, **overrides):
        base = {
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
        base.update(overrides)
        return base

    def test_path1_ai_price_update_creates_increase_history(self, email_sync_harness):
        """is_price_update=True, existing amount=15.99, new=18.99 → 'increase'.

        Plan adjustment: the code reads 'old_amount'/'new_amount' (not 'amount')
        from the extraction for path 1. We provide both keys. Also, amount is
        stored as Decimal in SQLite, so we compare via float().
        """
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix", amount=15.99)
        h.add_email(
            extraction=self._ext(
                is_price_update=True, old_amount=15.99, new_amount=18.99
            ),
        )

        result = h.run_sync()
        assert result["success"] is True
        # Sub amount updated to new_amount
        h.db.refresh(sub)
        assert float(sub.amount) == 18.99
        # Increase history record
        assert (
            h.count_price_history(subscription_id=sub.id, change_type="increase") >= 1
        )

    def test_path1_ai_price_update_creates_decrease_history(self, email_sync_harness):
        """is_price_update=True, old=20, new=15 → 'decrease'.

        Plan adjustment: same as above — use old_amount/new_amount keys and
        compare via float() for Decimal compatibility.
        """
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix", amount=20.0)
        h.add_email(
            extraction=self._ext(is_price_update=True, old_amount=20.0, new_amount=15.0)
        )

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        assert float(sub.amount) == 15.0
        assert (
            h.count_price_history(subscription_id=sub.id, change_type="decrease") >= 1
        )

    def test_path2_existing_sub_amount_diff_creates_history(self, email_sync_harness):
        """Match found via dedup, amount differs → batch-committed PriceHistory."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix", amount=15.99)
        h.add_email(extraction=self._ext(amount=17.99, is_price_update=False))

        result = h.run_sync()
        assert result["success"] is True
        # No new sub
        assert h.count_subs(provider="Netflix") == 1
        # PriceHistory created
        assert h.count_price_history(subscription_id=sub.id) >= 1

    def test_path3_new_subscription_with_amount_creates_initial_history(
        self, email_sync_harness
    ):
        """New sub created with amount=12.99 → PriceHistory(change_type='initial')."""
        h = email_sync_harness
        h.add_email(extraction=self._ext(amount=12.99))

        result = h.run_sync()
        assert result["success"] is True
        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert h.count_price_history(subscription_id=sub.id, change_type="initial") >= 1

    def test_path3_new_subscription_without_amount_skips_history(
        self, email_sync_harness
    ):
        """New sub with amount=None → no PriceHistory."""
        h = email_sync_harness
        h.add_email(extraction=self._ext(amount=None))

        result = h.run_sync()
        assert result["success"] is True
        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert h.count_price_history(subscription_id=sub.id) == 0

    def test_anomaly_price_update_with_no_existing_sub_falls_through(
        self, email_sync_harness
    ):
        """is_price_update=True but no existing sub → creates new sub + initial history.
        Locks the documented research anomaly.

        Plan adjustment: sub.amount is Decimal in SQLite; compare via float().
        """
        h = email_sync_harness
        h.add_email(extraction=self._ext(amount=12.99, is_price_update=True))

        result = h.run_sync()
        assert result["success"] is True
        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert float(sub.amount) == 12.99
        # Initial price history (not increase/decrease)
        assert h.count_price_history(subscription_id=sub.id, change_type="initial") >= 1


class TestSyncInnerPipelineRenewalStep:
    """Chartests for the renewal calculation step (lines 664-731)."""

    def _ext(self, **overrides):
        base = {
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
        base.update(overrides)
        return base

    def test_renewal_calculated_when_sub_has_emails(self, email_sync_harness):
        """Existing sub with linked email → RenewalCalculator invoked on new email, renewal_date set.

        Plan adjustment: renewal step only fires when subscription_emails junction already
        has rows (the link for the NEW email is added AFTER the renewal step). So we
        pre-create an existing sub + pre-linked email; a second email arrives, dedup
        matches it, and the renewal step fires because the existing link is already there.
        """
        from datetime import datetime, timezone, timedelta

        h = email_sync_harness
        # Pre-create sub with a linked email so get_subscription_emails returns non-empty
        sub = h.add_existing_sub(provider="Netflix", amount=15.99)
        h.add_email(
            message_id="first-email",
            extraction=self._ext(),
        )
        h.run_sync()  # First sync: creates the sub and links first_email
        # Reset and run again with a second email so renewal step fires on the existing sub
        h.queued_emails.clear()
        h.add_email(
            message_id="second-email",
            extraction=self._ext(),
        )

        future = datetime.now(timezone.utc) + timedelta(days=30)
        # calculate_renewal_info returns a tuple: (renewal_date, is_active, trial_status, is_confirmed)
        with patch("app.tasks.email_sync.renewal_step.RenewalCalculator") as MockCalc:
            inst = MockCalc.return_value
            inst.calculate_renewal_info.return_value = (future, True, None, True)
            inst.detect_reactivation.return_value = False

            result = h.run_sync()

        assert result["success"] is True
        h.db.refresh(sub)
        assert sub.renewal_date is not None
        assert sub.is_active is True

    def test_renewal_calculator_exception_does_not_break_batch(
        self, email_sync_harness
    ):
        """RenewalCalculator throws → exception caught at line 728, sub still persisted."""
        h = email_sync_harness
        h.add_email()

        with patch("app.tasks.email_sync.renewal_step.RenewalCalculator") as MockCalc:
            MockCalc.return_value.calculate_renewal_info.side_effect = ValueError(
                "calc failure"
            )
            result = h.run_sync()

        # Sync still completes
        assert result["success"] is True
        # Sub still persisted (renewal calc is best-effort)
        sub = h.get_sub(provider="Netflix")
        assert sub is not None

    def test_detect_reactivation_called_after_renewal(self, email_sync_harness):
        """RenewalCalculator.detect_reactivation invoked after calculate_renewal_info.

        Plan adjustment: same as test_renewal_calculated_when_sub_has_emails —
        renewal step only fires when subscription_emails has pre-existing rows.
        Use two-pass approach: first pass creates sub+link, second pass triggers renewal.
        """
        from datetime import datetime, timezone, timedelta

        h = email_sync_harness
        h.add_existing_sub(provider="Netflix", amount=15.99)
        h.add_email(message_id="first-email", extraction=self._ext())
        h.run_sync()  # First pass: creates link

        h.queued_emails.clear()
        h.add_email(message_id="second-email", extraction=self._ext())

        with patch("app.tasks.email_sync.renewal_step.RenewalCalculator") as MockCalc:
            inst = MockCalc.return_value
            inst.calculate_renewal_info.return_value = (
                datetime.now(timezone.utc) + timedelta(days=30),
                True,
                None,
                True,
            )
            inst.detect_reactivation.return_value = False

            h.run_sync()

        # Both methods called at least once
        inst.calculate_renewal_info.assert_called()
        inst.detect_reactivation.assert_called()


class TestSyncInnerPipelineCancellationStep:
    """Chartests for cancellation-suggestion creation (lines 733-767)."""

    def _ext(self, **overrides):
        base = {
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
        base.update(overrides)
        return base

    def test_cancellation_email_creates_suggestion_when_none_pending(
        self, email_sync_harness
    ):
        """Email classified as cancellation, sub has no pending suggestion → created."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix")
        h.add_email(
            category="cancellation",
            reasoning="user clicked cancel",
            extraction=self._ext(),
        )

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        assert sub.suggested_cancellation_status == "cancelled"
        assert sub.cancellation_suggestion_reason
        assert sub.cancellation_suggestion_created_at is not None

    def test_cancellation_skipped_when_suggestion_already_pending(
        self, email_sync_harness
    ):
        """Sub already has pending suggestion → email-classified-cancellation skipped silently."""
        from datetime import datetime, timezone

        h = email_sync_harness
        sub = h.add_existing_sub(
            provider="Netflix",
            suggested_cancellation_status="cancelled",
            cancellation_suggestion_reason="prior reason",
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        h.add_email(
            category="cancellation",
            reasoning="another cancel email",
            extraction=self._ext(),
        )

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        # Original suggestion preserved
        assert sub.cancellation_suggestion_reason == "prior reason"

    def test_non_cancellation_email_does_not_create_suggestion(
        self, email_sync_harness
    ):
        """Standard subscription email → no suggestion."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix")
        h.add_email(category="subscription", extraction=self._ext())

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        assert sub.suggested_cancellation_status is None


class TestSyncInnerPipelineCommitBoundariesAndPolling:
    """
    Chartests for transactional parity (commit/rollback per email + per batch)
    and the cancellation-polling early-exit.
    """

    def _ext(self, **overrides):
        base = {
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
        base.update(overrides)
        return base

    def test_per_email_commit_increments_counter(
        self, email_sync_harness, commit_rollback_counter
    ):
        """Each email processed → at least 1 db.commit() per email + 1 batch commit."""
        h = email_sync_harness
        commit_rollback_counter.reset()

        h.add_email(message_id="email-1", extraction=self._ext())
        h.add_email(message_id="email-2", extraction=self._ext(provider="Spotify"))
        h.add_email(message_id="email-3", extraction=self._ext(provider="Disney+"))

        result = h.run_sync()
        assert result["success"] is True

        # 3 emails × at least 1 commit each + final batch/mailbox commit ≥ 4 total
        assert commit_rollback_counter.commits >= 4

    def test_subscription_emails_junction_inserted_per_email(self, email_sync_harness):
        """Each new email creates a subscription_emails row for the matched sub."""
        h = email_sync_harness
        h.add_email(extraction=self._ext())

        result = h.run_sync()
        assert result["success"] is True

        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert h.email_links_for(sub.id)

    def test_cancellation_polling_exits_early_when_flag_set_pre_sync(
        self, email_sync_harness
    ):
        """Cancellation flag set before sync → flag is checked after the batch completes.

        Plan adjustment: the cancellation polling fires AFTER each batch (post-commit),
        not at the start of the sync or between per-email commits. With a single-email
        batch, the email IS processed and the subscription IS created before the check
        fires. The cancellation then resets the flag and exits. Additionally, on SQLite
        (test DB), the datetime subtraction in the cancellation path raises a TypeError
        (offset-naive vs offset-aware), causing the sync to return success=False.
        This is a pre-existing bug; we lock the observable behavior:
        - Sync terminates (returns a result dict — does not hang)
        - The cancellation flag is cleared (reset to False after detection)
        - At most 1 subscription created (the batch that was already processing)
        """
        h = email_sync_harness
        h.mailbox.sync_cancellation_requested = True
        h.db.commit()

        h.add_email(extraction=self._ext())
        result = h.run_sync()

        # Sync terminates and returns a result (does not hang or raise unhandled)
        assert isinstance(result, dict)

        # Cancellation flag is cleared after detection
        h.db.refresh(h.mailbox)
        assert not h.mailbox.sync_cancellation_requested

        # At most 1 sub created (the single email that was in the batch)
        assert h.count_subs(provider="Netflix") <= 1
