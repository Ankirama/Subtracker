"""
Comprehensive tests for budget alerts task.

Tests budget monitoring, alert creation, and email notifications.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.user import User
from app.models.subscription import Subscription
from app.tasks.budget_alerts import (
    should_send_budget_alert,
    create_budget_notification,
    send_budget_alert_email,
    check_budget_alerts
)


@pytest.fixture
def test_budget(db_session: Session, test_user: User) -> Budget:
    """Create a test budget."""
    budget = Budget(
        user_id=test_user.id,
        name="Streaming Services",
        limit_amount=50.00,
        period="monthly",
        category="streaming",
        alert_enabled="true",
        alert_threshold=0.8
    )
    db_session.add(budget)
    db_session.commit()
    db_session.refresh(budget)
    return budget


@pytest.fixture
def test_subscriptions_for_budget(db_session: Session, test_user: User, test_mailbox) -> list[Subscription]:
    """Create test subscriptions for budget testing."""
    subscriptions = [
        Subscription(
            user_id=test_user.id,
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
        ),
        Subscription(
            user_id=test_user.id,
            mailbox_id=test_mailbox.id,
            provider="Spotify",
            amount=9.99,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc)
        ),
        Subscription(
            user_id=test_user.id,
            mailbox_id=test_mailbox.id,
            provider="Disney+",
            amount=12.99,
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
    ]

    for sub in subscriptions:
        db_session.add(sub)

    db_session.commit()
    for sub in subscriptions:
        db_session.refresh(sub)

    return subscriptions


class TestShouldSendBudgetAlert:
    """Tests for should_send_budget_alert function."""

    def test_no_recent_alert(self, db_session: Session, test_budget: Budget):
        """Should send alert when no recent alerts exist."""
        result = should_send_budget_alert(str(test_budget.id), 'warning', db_session)
        assert result is True

    def test_recent_alert_same_type(self, db_session: Session, test_budget: Budget, test_user: User):
        """Should not send alert when same type alert sent within 24h."""
        # Create recent alert
        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.BUDGET_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Budget Alert",
            message="Test alert",
            related_budget_id=str(test_budget.id),
            notification_metadata={'alert_type': 'warning'},
            created_at=datetime.now(timezone.utc) - timedelta(hours=12)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_budget_alert(str(test_budget.id), 'warning', db_session)
        assert result is False

    def test_recent_alert_different_type(self, db_session: Session, test_budget: Budget, test_user: User):
        """Should send alert when type changed (warning -> exceeded)."""
        # Create recent warning alert
        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.BUDGET_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Budget Alert",
            message="Test alert",
            related_budget_id=str(test_budget.id),
            notification_metadata={'alert_type': 'warning'},
            created_at=datetime.now(timezone.utc) - timedelta(hours=12)
        )
        db_session.add(notification)
        db_session.commit()

        # Should allow exceeded alert even though warning was recent
        result = should_send_budget_alert(str(test_budget.id), 'exceeded', db_session)
        assert result is True

    def test_old_alert_allows_new(self, db_session: Session, test_budget: Budget, test_user: User):
        """Should send alert when previous alert is older than 24h."""
        # Create old alert
        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.BUDGET_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Budget Alert",
            message="Test alert",
            related_budget_id=str(test_budget.id),
            notification_metadata={'alert_type': 'warning'},
            created_at=datetime.now(timezone.utc) - timedelta(hours=25)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_budget_alert(str(test_budget.id), 'warning', db_session)
        assert result is True


class TestCreateBudgetNotification:
    """Tests for create_budget_notification function."""

    def test_create_warning_notification(self, db_session: Session, test_budget: Budget):
        """Should create medium priority warning notification."""
        message = "Budget approaching limit"

        notification = create_budget_notification(test_budget, 'warning', message, db_session)

        assert notification.id is not None
        assert notification.user_id == test_budget.user_id
        assert notification.type == NotificationType.BUDGET_ALERT
        assert notification.priority == NotificationPriority.MEDIUM
        assert notification.title == f"Budget Alert: {test_budget.name}"
        assert notification.message == message
        assert str(notification.related_budget_id) == str(test_budget.id)
        assert notification.notification_metadata['alert_type'] == 'warning'
        assert notification.notification_metadata['budget_name'] == test_budget.name
        assert notification.notification_metadata['category'] == test_budget.category

    def test_create_exceeded_notification(self, db_session: Session, test_budget: Budget):
        """Should create high priority exceeded notification."""
        message = "Budget exceeded!"

        notification = create_budget_notification(test_budget, 'exceeded', message, db_session)

        assert notification.priority == NotificationPriority.HIGH
        assert notification.notification_metadata['alert_type'] == 'exceeded'

    def test_notification_persisted_to_db(self, db_session: Session, test_budget: Budget):
        """Should persist notification to database."""
        message = "Test message"

        notification = create_budget_notification(test_budget, 'warning', message, db_session)

        # Query from DB to verify persistence
        db_notification = db_session.query(Notification).filter(
            Notification.id == notification.id
        ).first()

        assert db_notification is not None
        assert db_notification.message == message


class TestSendBudgetAlertEmail:
    """Tests for send_budget_alert_email function."""

    @pytest.mark.asyncio
    @patch('app.tasks.budget_alerts.EmailService.send_email', new_callable=AsyncMock)
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    async def test_send_warning_email(
        self,
        mock_get_budget_status: MagicMock,
        mock_send_email: AsyncMock,
        test_budget: Budget,
        test_user: User
    ):
        """Should send warning email with correct content."""

        # Mock budget status
        mock_status = MagicMock()
        mock_status.currency = "EUR"
        mock_status.current_spending = 42.00
        mock_status.limit_amount = 50.00
        mock_status.remaining = 8.00
        mock_status.percentage_used = 84.0
        mock_status.period_start = "2025-11-01"
        mock_status.period_end = "2025-11-30"
        mock_get_budget_status.return_value = mock_status

        message = "Budget approaching limit"

        await send_budget_alert_email(test_budget, 'warning', message, test_user)

        # Verify email was sent
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[1]

        assert call_args['to_email'] == test_user.email
        assert "Budget Alert" in call_args['subject']
        assert test_budget.name in call_args['subject']
        assert "Approaching Limit" in call_args['html_content']
        assert "#F59E0B" in call_args['html_content']  # Warning color
        assert "84.0%" in call_args['html_content']
        assert message in call_args['html_content']

    @pytest.mark.asyncio
    @patch('app.tasks.budget_alerts.EmailService.send_email', new_callable=AsyncMock)
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    async def test_send_exceeded_email(
        self,
        mock_get_budget_status: MagicMock,
        mock_send_email: AsyncMock,
        test_budget: Budget,
        test_user: User
    ):
        """Should send exceeded email with high urgency."""

        # Mock budget status
        mock_status = MagicMock()
        mock_status.currency = "EUR"
        mock_status.current_spending = 55.00
        mock_status.limit_amount = 50.00
        mock_status.remaining = -5.00
        mock_status.percentage_used = 110.0
        mock_status.period_start = "2025-11-01"
        mock_status.period_end = "2025-11-30"
        mock_get_budget_status.return_value = mock_status

        message = "Budget exceeded!"

        await send_budget_alert_email(test_budget, 'exceeded', message, test_user)

        # Verify email was sent
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[1]

        assert "Over Budget" in call_args['html_content']
        assert "#EF4444" in call_args['html_content']  # Exceeded color
        assert "-5.00" in call_args['html_content']  # Negative remaining

    @pytest.mark.asyncio
    @patch('app.tasks.budget_alerts.EmailService.send_email', new_callable=AsyncMock)
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    async def test_email_contains_budget_details(
        self,
        mock_get_budget_status: MagicMock,
        mock_send_email: AsyncMock,
        test_budget: Budget,
        test_user: User
    ):
        """Should include all budget details in email."""

        mock_status = MagicMock()
        mock_status.currency = "EUR"
        mock_status.current_spending = 42.00
        mock_status.limit_amount = 50.00
        mock_status.remaining = 8.00
        mock_status.percentage_used = 84.0
        mock_status.period_start = "2025-11-01"
        mock_status.period_end = "2025-11-30"
        mock_get_budget_status.return_value = mock_status

        await send_budget_alert_email(test_budget, 'warning', "Test", test_user)

        call_args = mock_send_email.call_args[1]
        html_content = call_args['html_content']

        assert str(mock_status.current_spending) in html_content
        assert str(mock_status.limit_amount) in html_content
        assert str(mock_status.remaining) in html_content
        assert f"{mock_status.percentage_used:.1f}%" in html_content
        assert mock_status.period_start in html_content
        assert mock_status.period_end in html_content
        assert test_budget.category.capitalize() in html_content


class TestCheckBudgetAlerts:
    """Tests for check_budget_alerts task."""

    @patch('app.tasks.budget_alerts.send_budget_alert_email')
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    def test_check_alerts_with_no_budgets(
        self,
        mock_get_budget_status: MagicMock,
        mock_send_email: MagicMock,
        db_session: Session
    ):
        """Should handle empty budget list gracefully."""
        result = check_budget_alerts()

        assert result['total_budgets_checked'] == 0
        assert result['alerts_created'] == 0
        assert result['emails_sent'] == 0
        mock_send_email.assert_not_called()

    @patch('app.tasks.budget_alerts.send_budget_alert_email')
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    @patch('app.tasks.budget_alerts.SessionLocal')
    def test_check_alerts_with_warning_budget(
        self,
        mock_session_local: MagicMock,
        mock_get_budget_status: MagicMock,
        mock_send_email: MagicMock,
        db_session: Session,
        test_budget: Budget,
        test_user: User
    ):
        """Should create warning alert when budget approaching limit."""
        mock_session_local.return_value = db_session

        # Mock budget status at 85% (warning threshold)
        mock_status = MagicMock()
        mock_status.status = 'warning'
        mock_status.currency = "EUR"
        mock_status.current_spending = 42.50
        mock_status.limit_amount = 50.00
        mock_status.percentage_used = 85.0
        mock_get_budget_status.return_value = mock_status

        result = check_budget_alerts()

        assert result['total_budgets_checked'] == 1
        assert result['alerts_created'] == 1
        assert result['emails_sent'] == 1

        # Verify notification was created
        notification = db_session.query(Notification).filter(
            Notification.related_budget_id == str(test_budget.id)
        ).first()

        assert notification is not None
        assert notification.priority == NotificationPriority.MEDIUM
        assert 'approaching' in notification.message.lower()
        mock_send_email.assert_called_once()

    @patch('app.tasks.budget_alerts.send_budget_alert_email')
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    @patch('app.tasks.budget_alerts.SessionLocal')
    def test_check_alerts_with_exceeded_budget(
        self,
        mock_session_local: MagicMock,
        mock_get_budget_status: MagicMock,
        mock_send_email: MagicMock,
        db_session: Session,
        test_budget: Budget,
        test_user: User
    ):
        """Should create high priority alert when budget exceeded."""
        mock_session_local.return_value = db_session

        # Mock budget status at 110% (exceeded)
        mock_status = MagicMock()
        mock_status.status = 'exceeded'
        mock_status.currency = "EUR"
        mock_status.current_spending = 55.00
        mock_status.limit_amount = 50.00
        mock_status.percentage_used = 110.0
        mock_get_budget_status.return_value = mock_status

        result = check_budget_alerts()

        assert result['alerts_created'] == 1

        # Verify notification priority
        notification = db_session.query(Notification).filter(
            Notification.related_budget_id == str(test_budget.id)
        ).first()

        assert notification.priority == NotificationPriority.HIGH
        assert 'exceeded' in notification.message.lower()

    @patch('app.tasks.budget_alerts.send_budget_alert_email')
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    @patch('app.tasks.budget_alerts.SessionLocal')
    def test_check_alerts_skips_disabled_budgets(
        self,
        mock_session_local: MagicMock,
        mock_get_budget_status: MagicMock,
        mock_send_email: MagicMock,
        db_session: Session,
        test_budget: Budget
    ):
        """Should not alert for budgets with alerts disabled."""
        mock_session_local.return_value = db_session

        # Disable alerts
        test_budget.alert_enabled = "false"
        db_session.commit()

        result = check_budget_alerts()

        assert result['total_budgets_checked'] == 0
        assert result['alerts_created'] == 0
        mock_send_email.assert_not_called()

    @patch('app.tasks.budget_alerts.send_budget_alert_email')
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    @patch('app.tasks.budget_alerts.SessionLocal')
    def test_check_alerts_respects_email_preferences(
        self,
        mock_session_local: MagicMock,
        mock_get_budget_status: MagicMock,
        mock_send_email: MagicMock,
        db_session: Session,
        test_budget: Budget,
        test_user: User
    ):
        """Should respect user email notification preferences."""
        mock_session_local.return_value = db_session

        # Disable email notifications
        test_user.settings = {'notifications': {'email_enabled': False}}
        db_session.commit()

        # Mock exceeded budget
        mock_status = MagicMock()
        mock_status.status = 'exceeded'
        mock_status.currency = "EUR"
        mock_status.current_spending = 55.00
        mock_status.limit_amount = 50.00
        mock_status.percentage_used = 110.0
        mock_get_budget_status.return_value = mock_status

        result = check_budget_alerts()

        # Should create notification but not send email
        assert result['alerts_created'] == 1
        assert result['emails_sent'] == 0
        mock_send_email.assert_not_called()

    @patch('app.tasks.budget_alerts.send_budget_alert_email')
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    @patch('app.tasks.budget_alerts.SessionLocal')
    def test_check_alerts_handles_errors_gracefully(
        self,
        mock_session_local: MagicMock,
        mock_get_budget_status: MagicMock,
        mock_send_email: MagicMock,
        db_session: Session,
        test_budget: Budget,
        test_user: User
    ):
        """Should continue processing other budgets if one fails."""
        mock_session_local.return_value = db_session

        # Create second budget
        budget2 = Budget(
            user_id=test_user.id,
            name="Shopping Budget",
            limit_amount=100.00,
            period="monthly",
            category="shopping",
            alert_enabled="true",
            alert_threshold=0.8
        )
        db_session.add(budget2)
        db_session.commit()

        # First budget raises error, second succeeds
        mock_status = MagicMock()
        mock_status.status = 'warning'
        mock_status.currency = "EUR"
        mock_status.current_spending = 85.00
        mock_status.limit_amount = 100.00
        mock_status.percentage_used = 85.0

        mock_get_budget_status.side_effect = [
            Exception("Test error"),
            mock_status
        ]

        result = check_budget_alerts()

        # Should process both budgets, create alert for second one
        assert result['total_budgets_checked'] == 2
        assert result['alerts_created'] == 1

    @patch('app.tasks.budget_alerts.send_budget_alert_email')
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    @patch('app.tasks.budget_alerts.SessionLocal')
    def test_check_alerts_prevents_duplicate_alerts(
        self,
        mock_session_local: MagicMock,
        mock_get_budget_status: MagicMock,
        mock_send_email: MagicMock,
        db_session: Session,
        test_budget: Budget,
        test_user: User
    ):
        """Should not send duplicate alerts within 24h."""
        mock_session_local.return_value = db_session

        # Create recent alert
        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.BUDGET_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Budget Alert",
            message="Test alert",
            related_budget_id=str(test_budget.id),
            notification_metadata={'alert_type': 'warning'},
            created_at=datetime.now(timezone.utc) - timedelta(hours=12)
        )
        db_session.add(notification)
        db_session.commit()

        # Mock warning status
        mock_status = MagicMock()
        mock_status.status = 'warning'
        mock_status.currency = "EUR"
        mock_status.current_spending = 42.50
        mock_status.limit_amount = 50.00
        mock_status.percentage_used = 85.0
        mock_get_budget_status.return_value = mock_status

        result = check_budget_alerts()

        # Should not create duplicate alert
        assert result['alerts_created'] == 0
        assert result['emails_sent'] == 0

    @patch('app.tasks.budget_alerts.send_budget_alert_email', new_callable=AsyncMock)
    @patch('app.tasks.budget_alerts.BudgetService.get_budget_status')
    @patch('app.tasks.budget_alerts.SessionLocal')
    def test_check_alerts_upgrades_warning_to_exceeded(
        self,
        mock_session_local: MagicMock,
        mock_get_budget_status: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_budget: Budget,
        test_user: User
    ):
        """Should send new alert when status upgrades from warning to exceeded."""
        mock_session_local.return_value = db_session

        # Create recent warning alert
        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.BUDGET_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Budget Alert",
            message="Warning",
            related_budget_id=str(test_budget.id),
            notification_metadata={'alert_type': 'warning'},
            created_at=datetime.now(timezone.utc) - timedelta(hours=12)
        )
        db_session.add(notification)
        db_session.commit()

        # Store ID before check_budget_alerts() to avoid DetachedInstanceError
        warning_notification_id = notification.id

        # Mock exceeded status
        mock_status = MagicMock()
        mock_status.status = 'exceeded'
        mock_status.currency = "EUR"
        mock_status.current_spending = 55.00
        mock_status.limit_amount = 50.00
        mock_status.percentage_used = 110.0
        mock_get_budget_status.return_value = mock_status

        result = check_budget_alerts()

        # Should create new exceeded alert
        assert result['alerts_created'] == 1

        # Verify it's a high priority exceeded alert
        exceeded_notification = db_session.query(Notification).filter(
            Notification.related_budget_id == str(test_budget.id),
            Notification.id != warning_notification_id
        ).first()

        assert exceeded_notification is not None
        assert exceeded_notification.priority == NotificationPriority.HIGH
        assert exceeded_notification.notification_metadata['alert_type'] == 'exceeded'
