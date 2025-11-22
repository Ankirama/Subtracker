"""
Comprehensive tests for price change monitoring task.

Tests price change detection, notifications, and email alerts.
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.notification import Notification, NotificationPreference, NotificationType, NotificationPriority
from app.models.user import User
from app.tasks.price_change_monitor import (
    detect_price_change,
    should_send_price_change_notification,
    create_price_change_notification,
    send_price_change_email,
    check_price_changes
)


@pytest.fixture
def subscription_with_price(db_session: Session, test_subscription: Subscription) -> Subscription:
    """Create a test subscription with price tracking metadata."""
    test_subscription.amount = Decimal("15.99")
    test_subscription.currency = "EUR"
    test_subscription.extraction_metadata = {
        'last_known_price': 15.99,
        'price_last_checked': datetime.now().isoformat()
    }
    db_session.commit()
    db_session.refresh(test_subscription)
    return test_subscription


class TestDetectPriceChange:
    """Tests for detect_price_change function."""

    def test_first_time_tracking(self, db_session: Session, test_subscription: Subscription):
        """Should initialize price tracking on first check."""
        test_subscription.amount = Decimal("15.99")
        test_subscription.extraction_metadata = None
        db_session.commit()

        has_changed, old_price, new_price = detect_price_change(test_subscription, db_session)

        assert has_changed is False
        assert old_price is None
        assert new_price is None
        # Verify metadata was initialized
        db_session.refresh(test_subscription)
        assert test_subscription.extraction_metadata is not None
        assert test_subscription.extraction_metadata['last_known_price'] == 15.99
        assert 'price_last_checked' in test_subscription.extraction_metadata

    def test_no_price_change(self, db_session: Session, subscription_with_price: Subscription):
        """Should return False when price unchanged."""
        has_changed, old_price, new_price = detect_price_change(subscription_with_price, db_session)

        assert has_changed is False
        assert old_price is None
        assert new_price is None
        # Verify timestamp updated
        db_session.refresh(subscription_with_price)
        assert 'price_last_checked' in subscription_with_price.extraction_metadata

    def test_price_increase_detected(self, db_session: Session, subscription_with_price: Subscription):
        """Should detect price increase."""
        # Change price
        subscription_with_price.amount = Decimal("19.99")
        db_session.commit()

        has_changed, old_price, new_price = detect_price_change(subscription_with_price, db_session)

        assert has_changed is True
        assert old_price == Decimal("15.99")
        assert new_price == Decimal("19.99")

    def test_price_decrease_detected(self, db_session: Session, subscription_with_price: Subscription):
        """Should detect price decrease."""
        # Change price
        subscription_with_price.amount = Decimal("12.99")
        db_session.commit()

        has_changed, old_price, new_price = detect_price_change(subscription_with_price, db_session)

        assert has_changed is True
        assert old_price == Decimal("15.99")
        assert new_price == Decimal("12.99")

    def test_handles_none_amount(self, db_session: Session, test_subscription: Subscription):
        """Should handle subscription with no amount."""
        test_subscription.amount = None
        db_session.commit()

        has_changed, old_price, new_price = detect_price_change(test_subscription, db_session)

        assert has_changed is False
        assert old_price is None
        assert new_price is None

    def test_small_price_change_detected(self, db_session: Session, subscription_with_price: Subscription):
        """Should detect even small price changes."""
        subscription_with_price.amount = Decimal("16.00")
        db_session.commit()

        has_changed, old_price, new_price = detect_price_change(subscription_with_price, db_session)

        assert has_changed is True
        assert old_price == Decimal("15.99")
        assert new_price == Decimal("16.00")

    def test_handles_empty_metadata(self, db_session: Session, test_subscription: Subscription):
        """Should handle subscription with empty metadata dict."""
        test_subscription.amount = Decimal("15.99")
        test_subscription.extraction_metadata = {}
        db_session.commit()

        has_changed, old_price, new_price = detect_price_change(test_subscription, db_session)

        assert has_changed is False
        assert test_subscription.extraction_metadata['last_known_price'] == 15.99


class TestShouldSendPriceChangeNotification:
    """Tests for should_send_price_change_notification function."""

    def test_should_send_for_active_subscription(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should send notification for active subscription with no recent alerts."""
        test_subscription.is_active = True
        db_session.commit()

        result = should_send_price_change_notification(test_subscription, db_session)
        assert result is True

    def test_should_not_send_for_inactive_subscription(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should not send notification for inactive subscription."""
        test_subscription.is_active = False
        db_session.commit()

        result = should_send_price_change_notification(test_subscription, db_session)
        assert result is False

    def test_should_not_send_duplicate_within_7_days(
        self,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should not send notification if one was sent recently."""
        test_subscription.is_active = True
        db_session.commit()

        # Create recent notification
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=test_subscription.id,
            type=NotificationType.PRICE_CHANGE,
            priority=NotificationPriority.MEDIUM,
            title="Price Change",
            message="Price changed",
            created_at=datetime.now(timezone.utc) - timedelta(days=3)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_price_change_notification(test_subscription, db_session)
        assert result is False

    def test_should_send_after_7_days(
        self,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should send notification if previous one is older than 7 days."""
        test_subscription.is_active = True
        db_session.commit()

        # Create old notification
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=test_subscription.id,
            type=NotificationType.PRICE_CHANGE,
            priority=NotificationPriority.MEDIUM,
            title="Price Change",
            message="Price changed",
            created_at=datetime.now(timezone.utc) - timedelta(days=8)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_price_change_notification(test_subscription, db_session)
        assert result is True


class TestCreatePriceChangeNotification:
    """Tests for create_price_change_notification function."""

    def test_create_notification_for_increase(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should create high/medium priority notification for price increase."""
        old_price = Decimal("15.99")
        new_price = Decimal("19.99")

        notification = create_price_change_notification(
            test_subscription, old_price, new_price, db_session
        )

        assert notification.id is not None
        assert notification.user_id == test_subscription.user_id
        assert notification.related_subscription_id == test_subscription.id
        assert notification.type == NotificationType.PRICE_CHANGE
        assert notification.priority == NotificationPriority.HIGH  # 25% increase > 20% threshold
        assert "📈" in notification.title
        assert "increased" in notification.message.lower()
        assert str(old_price) in notification.message
        assert str(new_price) in notification.message

        # Check metadata
        metadata = notification.notification_metadata
        assert metadata['old_price'] == float(old_price)
        assert metadata['new_price'] == float(new_price)
        assert metadata['is_increase'] is True
        assert metadata['price_difference'] == 4.0
        assert metadata['change_percent'] == pytest.approx(25.0, rel=0.1)

    def test_create_notification_for_large_increase(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should create HIGH priority notification for large price increase (>20%)."""
        old_price = Decimal("10.00")
        new_price = Decimal("15.00")  # 50% increase

        notification = create_price_change_notification(
            test_subscription, old_price, new_price, db_session
        )

        assert notification.priority == NotificationPriority.HIGH
        assert notification.notification_metadata['change_percent'] == pytest.approx(50.0, rel=0.1)

    def test_create_notification_for_decrease(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should create low priority notification for price decrease."""
        old_price = Decimal("19.99")
        new_price = Decimal("15.99")

        notification = create_price_change_notification(
            test_subscription, old_price, new_price, db_session
        )

        assert notification.priority == NotificationPriority.LOW
        assert "📉" in notification.title
        assert "decreased" in notification.message.lower()

        # Check metadata
        metadata = notification.notification_metadata
        assert metadata['is_increase'] is False
        assert metadata['price_difference'] == -4.0

    def test_notification_includes_currency(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should include currency in notification."""
        test_subscription.currency = "USD"
        db_session.commit()

        notification = create_price_change_notification(
            test_subscription, Decimal("10.00"), Decimal("12.00"), db_session
        )

        assert "USD" in notification.message
        assert notification.notification_metadata['currency'] == "USD"

    def test_notification_persisted_to_db(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should persist notification to database."""
        notification = create_price_change_notification(
            test_subscription, Decimal("10.00"), Decimal("12.00"), db_session
        )

        # Query from DB to verify persistence
        db_notification = db_session.query(Notification).filter(
            Notification.id == notification.id
        ).first()

        assert db_notification is not None
        assert db_notification.type == NotificationType.PRICE_CHANGE


class TestSendPriceChangeEmail:
    """Tests for send_price_change_email function."""

    @pytest.mark.asyncio
    @patch('app.tasks.price_change_monitor.EmailService')
    async def test_send_email_for_price_increase(
        self,
        mock_email_service_class: MagicMock,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should send email with increase styling and messaging."""
        # Create notification
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=test_subscription.id,
            type=NotificationType.PRICE_CHANGE,
            priority=NotificationPriority.MEDIUM,
            title="Price Change",
            message="Price increased",
            notification_metadata={
                'old_price': 15.99,
                'new_price': 19.99,
                'price_difference': 4.0,
                'change_percent': 25.0,
                'is_increase': True
            }
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        # Mock email service
        mock_service = MagicMock()
        mock_service.send_email.return_value = (True, None)
        mock_email_service_class.return_value = mock_service

        success, error = await send_price_change_email(
            notification, test_user, test_subscription, db_session
        )

        assert success is True
        assert error is None

        # Verify email was sent with correct styling
        mock_service.send_email.assert_called_once()
        call_args = mock_service.send_email.call_args[1]

        assert call_args['to_email'] == test_user.email
        assert "📈" in call_args['subject']
        assert "Increased" in call_args['subject']
        assert "#e53e3e" in call_args['html_content']  # Red color for increase
        assert "increased" in call_args['html_content'].lower()

        # Verify notification updated
        db_session.refresh(notification)
        assert notification.email_sent is True
        assert notification.email_sent_at is not None

    @pytest.mark.asyncio
    @patch('app.tasks.price_change_monitor.EmailService')
    async def test_send_email_for_price_decrease(
        self,
        mock_email_service_class: MagicMock,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should send email with decrease styling and messaging."""
        # Create notification
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=test_subscription.id,
            type=NotificationType.PRICE_CHANGE,
            priority=NotificationPriority.LOW,
            title="Price Change",
            message="Price decreased",
            notification_metadata={
                'old_price': 19.99,
                'new_price': 15.99,
                'price_difference': -4.0,
                'change_percent': 20.0,
                'is_increase': False
            }
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        # Mock email service
        mock_service = MagicMock()
        mock_service.send_email.return_value = (True, None)
        mock_email_service_class.return_value = mock_service

        success, error = await send_price_change_email(
            notification, test_user, test_subscription, db_session
        )

        assert success is True

        # Verify email styling
        call_args = mock_service.send_email.call_args[1]
        assert "📉" in call_args['subject']
        assert "Decreased" in call_args['subject']
        assert "#38a169" in call_args['html_content']  # Green color for decrease
        assert "decreased" in call_args['html_content'].lower()

    @pytest.mark.asyncio
    @patch('app.tasks.price_change_monitor.EmailService')
    async def test_email_contains_price_comparison(
        self,
        mock_email_service_class: MagicMock,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should include detailed price comparison in email."""
        test_subscription.currency = "EUR"
        test_subscription.billing_cycle = "monthly"
        db_session.commit()

        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=test_subscription.id,
            type=NotificationType.PRICE_CHANGE,
            priority=NotificationPriority.MEDIUM,
            title="Price Change",
            message="Price changed",
            notification_metadata={
                'old_price': 15.99,
                'new_price': 19.99,
                'price_difference': 4.0,
                'change_percent': 25.0,
                'is_increase': True
            }
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        mock_service = MagicMock()
        mock_service.send_email.return_value = (True, None)
        mock_email_service_class.return_value = mock_service

        await send_price_change_email(notification, test_user, test_subscription, db_session)

        call_args = mock_service.send_email.call_args[1]
        html_content = call_args['html_content']

        assert "EUR 15.99" in html_content  # Old price
        assert "EUR 19.99" in html_content  # New price
        assert "EUR 4.00" in html_content  # Difference
        assert "25.0%" in html_content  # Percentage
        assert "Monthly" in html_content  # Billing cycle

    @pytest.mark.asyncio
    @patch('app.tasks.price_change_monitor.EmailService')
    async def test_handles_email_send_failure(
        self,
        mock_email_service_class: MagicMock,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should handle email send failures gracefully."""
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=test_subscription.id,
            type=NotificationType.PRICE_CHANGE,
            priority=NotificationPriority.MEDIUM,
            title="Price Change",
            message="Price changed",
            notification_metadata={
                'old_price': 15.99,
                'new_price': 19.99,
                'price_difference': 4.0,
                'change_percent': 25.0,
                'is_increase': True
            }
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        # Mock email failure
        mock_service = MagicMock()
        mock_service.send_email.return_value = (False, "SMTP connection failed")
        mock_email_service_class.return_value = mock_service

        success, error = await send_price_change_email(
            notification, test_user, test_subscription, db_session
        )

        assert success is False
        assert error == "SMTP connection failed"

        # Verify notification updated with error
        db_session.refresh(notification)
        assert notification.email_sent is False
        assert notification.email_error == "SMTP connection failed"


class TestCheckPriceChanges:
    """Tests for check_price_changes task."""

    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_no_subscriptions(self, mock_session_local: MagicMock, db_session: Session):
        """Should handle empty subscription list gracefully."""
        mock_session_local.return_value = db_session

        result = check_price_changes()

        assert result['status'] == 'success'
        assert result['price_changes_detected'] == 0
        assert result['notifications_created'] == 0
        assert result['emails_sent'] == 0

    @patch('app.tasks.price_change_monitor.send_price_change_email', new_callable=AsyncMock)
    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_detects_price_increase(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should detect price increase and create notification."""
        mock_session_local.return_value = db_session
        # Configure AsyncMock to return a tuple
        async def async_email_result(*args, **kwargs):
            return (True, None)
        mock_send_email.side_effect = async_email_result

        # Setup subscription with price increase
        test_subscription.amount = Decimal("19.99")
        test_subscription.is_active = True
        test_subscription.extraction_metadata = {'last_known_price': 15.99}
        db_session.commit()

        # Store ID before check_price_changes() to avoid DetachedInstanceError
        subscription_id = test_subscription.id

        result = check_price_changes()

        assert result['status'] == 'success'
        assert result['price_changes_detected'] == 1
        assert result['notifications_created'] == 1

        # Verify notification was created
        notification = db_session.query(Notification).filter(
            Notification.related_subscription_id == subscription_id
        ).first()
        assert notification is not None
        assert notification.type == NotificationType.PRICE_CHANGE

    @patch('app.tasks.price_change_monitor.send_price_change_email', new_callable=AsyncMock)
    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_respects_user_preferences(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should respect notification preferences."""
        mock_session_local.return_value = db_session
        # Configure AsyncMock to return a tuple
        async def async_email_result(*args, **kwargs):
            return (True, None)
        mock_send_email.side_effect = async_email_result

        # Disable notifications
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.PRICE_CHANGE,
            enabled=False,
            email_enabled=False
        )
        db_session.add(pref)

        # Setup price change
        test_subscription.amount = Decimal("19.99")
        test_subscription.is_active = True
        test_subscription.extraction_metadata = {'last_known_price': 15.99}
        db_session.commit()

        result = check_price_changes()

        # Should detect change but not create notification
        assert result['price_changes_detected'] == 1
        assert result['notifications_created'] == 0
        mock_send_email.assert_not_called()

    @patch('app.tasks.price_change_monitor.send_price_change_email', new_callable=AsyncMock)
    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_sends_email_when_enabled(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_subscription: Subscription,
        test_user: User
    ):
        """Should send email when email notifications enabled."""
        mock_session_local.return_value = db_session
        # Configure AsyncMock to return a tuple
        async def async_email_result(*args, **kwargs):
            return (True, None)
        mock_send_email.side_effect = async_email_result

        # Enable email notifications
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.PRICE_CHANGE,
            enabled=True,
            email_enabled=True
        )
        db_session.add(pref)

        # Setup price change
        test_subscription.amount = Decimal("19.99")
        test_subscription.is_active = True
        test_subscription.extraction_metadata = {'last_known_price': 15.99}
        db_session.commit()

        result = check_price_changes()

        assert result['emails_sent'] == 1
        mock_send_email.assert_called_once()

    @patch('app.tasks.price_change_monitor.send_price_change_email', new_callable=AsyncMock)
    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_updates_price_after_notification(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should update last_known_price after sending notification."""
        mock_session_local.return_value = db_session
        # Configure AsyncMock to return a tuple
        async def async_email_result(*args, **kwargs):
            return (True, None)
        mock_send_email.side_effect = async_email_result

        test_subscription.amount = Decimal("19.99")
        test_subscription.is_active = True
        test_subscription.extraction_metadata = {'last_known_price': 15.99}
        db_session.commit()

        # Store ID before check_price_changes() to avoid DetachedInstanceError
        subscription_id = test_subscription.id

        check_price_changes()

        # Expire all objects to force fresh load from database
        db_session.expire_all()

        # Verify metadata was updated - query fresh from database
        updated_subscription = db_session.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        assert updated_subscription.extraction_metadata['last_known_price'] == 19.99
        assert 'price_change_detected_at' in updated_subscription.extraction_metadata

    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_handles_errors_gracefully(
        self,
        mock_session_local: MagicMock,
        db_session: Session
    ):
        """Should handle errors and return error status."""
        # Mock session to raise exception
        mock_session_local.side_effect = Exception("Database connection failed")

        result = check_price_changes()

        assert result['status'] == 'error'
        assert 'error' in result
        assert 'Database connection failed' in result['error']

    @patch('app.tasks.price_change_monitor.send_price_change_email', new_callable=AsyncMock)
    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_skips_inactive_subscriptions(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should not notify for inactive subscriptions."""
        mock_session_local.return_value = db_session

        test_subscription.amount = Decimal("19.99")
        test_subscription.is_active = False  # Inactive
        test_subscription.extraction_metadata = {'last_known_price': 15.99}
        db_session.commit()

        result = check_price_changes()

        # Price change detected but notification not created due to inactive status
        assert result['notifications_created'] == 0
        mock_send_email.assert_not_called()

    @patch('app.tasks.price_change_monitor.send_price_change_email', new_callable=AsyncMock)
    @patch('app.tasks.price_change_monitor.SessionLocal')
    def test_skips_subscriptions_without_price(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should skip subscriptions with no amount."""
        mock_session_local.return_value = db_session

        test_subscription.amount = None
        test_subscription.is_active = True
        db_session.commit()

        result = check_price_changes()

        assert result['price_changes_detected'] == 0
        mock_send_email.assert_not_called()
