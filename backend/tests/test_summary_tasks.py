"""Comprehensive tests for summary tasks."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.models.notification import (
    NotificationPreference,
    NotificationType,
    Notification,
)
from app.models.user import User
from app.tasks.summary_tasks import send_weekly_summaries, send_monthly_summaries


class TestSendWeeklySummaries:
    """Tests for send_weekly_summaries task."""

    @patch("app.tasks.summary_tasks.EmailService")
    @patch("app.tasks.summary_tasks.EmailTemplates.generate_summary_email")
    @patch("app.tasks.summary_tasks.SummaryService.generate_weekly_summary")
    @patch("app.tasks.summary_tasks.SessionLocal")
    def test_sends_summaries_on_correct_day(
        self,
        mock_session_local: MagicMock,
        mock_generate_summary: MagicMock,
        mock_generate_email: MagicMock,
        mock_email_service_class: MagicMock,
        db_session: Session,
        test_user: User,
    ):
        """Should send summaries on user's preferred day."""
        mock_session_local.return_value = db_session

        # Create preference for current day
        current_day = datetime.now().weekday()
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.WEEKLY_SUMMARY,
            enabled=True,
            email_enabled=True,
            summary_day_of_week=current_day,
        )
        db_session.add(pref)
        db_session.commit()

        # Mock summary data
        mock_generate_summary.return_value = {
            "total_monthly_cost": 150.00,
            "total_subscriptions": 5,
            "active_subscriptions": 4,
        }
        mock_generate_email.return_value = "<html>Summary</html>"

        # Mock email service
        mock_email_service = MagicMock()
        mock_email_service.send_email.return_value = (True, None)
        mock_email_service_class.return_value = mock_email_service

        result = send_weekly_summaries()

        assert result["sent"] == 1
        mock_email_service.send_email.assert_called_once()

    @patch("app.tasks.summary_tasks.SummaryService.generate_weekly_summary")
    @patch("app.tasks.summary_tasks.SessionLocal")
    def test_creates_in_app_notification(
        self,
        mock_session_local: MagicMock,
        mock_generate_summary: MagicMock,
        db_session: Session,
        test_user: User,
    ):
        """Should create in-app notification if enabled."""
        mock_session_local.return_value = db_session

        current_day = datetime.now().weekday()
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.WEEKLY_SUMMARY,
            enabled=True,
            in_app_enabled=True,
            email_enabled=False,
            summary_day_of_week=current_day,
        )
        db_session.add(pref)
        db_session.commit()

        mock_generate_summary.return_value = {
            "total_monthly_cost": 150.00,
            "total_subscriptions": 5,
        }

        # Store ID before send_weekly_summaries() to avoid DetachedInstanceError
        user_id = test_user.id

        send_weekly_summaries()

        # Verify notification was created
        notification = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.type == NotificationType.WEEKLY_SUMMARY,
            )
            .first()
        )

        assert notification is not None
        assert "150.00" in notification.message

    @patch("app.tasks.summary_tasks.SessionLocal")
    def test_handles_no_preferences(
        self, mock_session_local: MagicMock, db_session: Session
    ):
        """Should handle no preferences gracefully."""
        mock_session_local.return_value = db_session

        result = send_weekly_summaries()

        assert result["sent"] == 0

    @patch("app.tasks.summary_tasks.EmailService")
    @patch("app.tasks.summary_tasks.EmailTemplates.generate_summary_email")
    @patch("app.tasks.summary_tasks.SummaryService.generate_weekly_summary")
    @patch("app.tasks.summary_tasks.SessionLocal")
    def test_handles_email_failure(
        self,
        mock_session_local: MagicMock,
        mock_generate_summary: MagicMock,
        mock_generate_email: MagicMock,
        mock_email_service_class: MagicMock,
        db_session: Session,
        test_user: User,
    ):
        """Should handle email failures gracefully."""
        mock_session_local.return_value = db_session

        current_day = datetime.now().weekday()
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.WEEKLY_SUMMARY,
            enabled=True,
            email_enabled=True,
            in_app_enabled=True,
            summary_day_of_week=current_day,
        )
        db_session.add(pref)
        db_session.commit()

        mock_generate_summary.return_value = {
            "total_monthly_cost": 150.00,
            "total_subscriptions": 5,
        }
        mock_generate_email.return_value = "<html>Summary</html>"

        # Mock email failure
        mock_email_service = MagicMock()
        mock_email_service.send_email.side_effect = Exception("SMTP error")
        mock_email_service_class.return_value = mock_email_service

        # Store ID before send_weekly_summaries() to avoid DetachedInstanceError
        user_id = test_user.id

        result = send_weekly_summaries()

        assert result["errors"] == 1

        # Verify notification has error
        notification = (
            db_session.query(Notification)
            .filter(Notification.user_id == user_id)
            .first()
        )
        assert notification.email_error is not None


class TestSendMonthlySummaries:
    """Tests for send_monthly_summaries task."""

    @patch("app.tasks.summary_tasks.EmailService")
    @patch("app.tasks.summary_tasks.EmailTemplates.generate_summary_email")
    @patch("app.tasks.summary_tasks.SummaryService.generate_monthly_summary")
    @patch("app.tasks.summary_tasks.SessionLocal")
    def test_sends_monthly_summaries_on_correct_day(
        self,
        mock_session_local: MagicMock,
        mock_generate_summary: MagicMock,
        mock_generate_email: MagicMock,
        mock_email_service_class: MagicMock,
        db_session: Session,
        test_user: User,
    ):
        """Should send monthly summaries on user's preferred day."""
        mock_session_local.return_value = db_session

        current_day = datetime.now().day
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.MONTHLY_SUMMARY,
            enabled=True,
            email_enabled=True,
            summary_day_of_month=current_day,
        )
        db_session.add(pref)
        db_session.commit()

        mock_generate_summary.return_value = {
            "total_monthly_cost": 200.00,
            "total_subscriptions": 8,
            "new_subscriptions_count": 2,
            "cancelled_subscriptions_count": 1,
        }
        mock_generate_email.return_value = "<html>Monthly Summary</html>"

        mock_email_service = MagicMock()
        mock_email_service.send_email.return_value = (True, None)
        mock_email_service_class.return_value = mock_email_service

        result = send_monthly_summaries()

        assert result["sent"] == 1

    @patch("app.tasks.summary_tasks.SessionLocal")
    def test_handles_errors_gracefully(self, mock_session_local: MagicMock):
        """Should handle errors and return error status."""
        mock_session_local.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            send_monthly_summaries()
