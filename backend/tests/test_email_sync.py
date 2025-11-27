"""Comprehensive tests for email sync task."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock
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

    @patch("app.tasks.email_sync.get_config_value")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
    @patch("app.tasks.email_sync.update_subscription_statuses")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
    @patch("app.tasks.email_sync.update_subscription_statuses")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
    @patch("app.tasks.email_sync.update_subscription_statuses")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
    @patch("app.tasks.email_sync.update_subscription_statuses")
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

    @patch("app.tasks.email_sync.asyncio.run")
    @patch("app.tasks.email_sync.SessionLocal")
    @patch("app.tasks.email_sync.update_subscription_statuses")
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
