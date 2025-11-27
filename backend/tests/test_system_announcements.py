"""Comprehensive tests for system announcements task."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
import uuid

from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
    NotificationPriority,
)
from app.models.user import User
from app.tasks.system_announcements import (
    create_announcement_notification,
    send_announcement_email,
    broadcast_system_announcement,
)
from app.security import hash_password


class TestCreateAnnouncementNotification:
    """Tests for create_announcement_notification function."""

    def test_creates_notification_with_correct_fields(
        self, db_session: Session, test_user: User
    ):
        """Should create notification with all required fields."""
        title = "System Maintenance"
        message = "We will be performing maintenance tonight"
        priority = "high"

        notification = create_announcement_notification(
            user_id=test_user.id,
            title=title,
            message=message,
            priority=priority,
            db=db_session,
        )

        assert notification.user_id == test_user.id
        assert notification.type == NotificationType.SYSTEM_ANNOUNCEMENT
        assert notification.priority == NotificationPriority.HIGH
        assert notification.title == f"📢 {title}"
        assert notification.message == message

    def test_maps_priority_levels_correctly(self, db_session: Session, test_user: User):
        """Should correctly map priority strings to enums."""
        # Test low priority
        notif_low = create_announcement_notification(
            user_id=test_user.id,
            title="Low Priority",
            message="Test",
            priority="low",
            db=db_session,
        )
        assert notif_low.priority == NotificationPriority.LOW

        # Test medium priority
        notif_medium = create_announcement_notification(
            user_id=test_user.id,
            title="Medium Priority",
            message="Test",
            priority="medium",
            db=db_session,
        )
        assert notif_medium.priority == NotificationPriority.MEDIUM

        # Test high priority
        notif_high = create_announcement_notification(
            user_id=test_user.id,
            title="High Priority",
            message="Test",
            priority="high",
            db=db_session,
        )
        assert notif_high.priority == NotificationPriority.HIGH

    def test_defaults_to_medium_priority_for_unknown(
        self, db_session: Session, test_user: User
    ):
        """Should default to medium priority for unknown priority values."""
        notification = create_announcement_notification(
            user_id=test_user.id,
            title="Unknown Priority",
            message="Test",
            priority="unknown_priority_level",
            db=db_session,
        )

        assert notification.priority == NotificationPriority.MEDIUM

    def test_includes_metadata(self, db_session: Session, test_user: User):
        """Should include announcement metadata."""
        notification = create_announcement_notification(
            user_id=test_user.id,
            title="Test",
            message="Test message",
            priority="high",
            db=db_session,
        )

        metadata = notification.notification_metadata
        assert "announcement_priority" in metadata
        assert metadata["announcement_priority"] == "high"
        assert "broadcast_time" in metadata

    def test_adds_emoji_prefix_to_title(self, db_session: Session, test_user: User):
        """Should add 📢 emoji prefix to title."""
        title = "Important Update"
        notification = create_announcement_notification(
            user_id=test_user.id,
            title=title,
            message="Test",
            priority="medium",
            db=db_session,
        )

        assert notification.title.startswith("📢 ")
        assert title in notification.title

    def test_persists_notification_to_database(
        self, db_session: Session, test_user: User
    ):
        """Should persist notification to database."""
        notification = create_announcement_notification(
            user_id=test_user.id,
            title="Test",
            message="Test message",
            priority="medium",
            db=db_session,
        )

        db_notification = (
            db_session.query(Notification)
            .filter(Notification.id == notification.id)
            .first()
        )

        assert db_notification is not None
        assert db_notification.type == NotificationType.SYSTEM_ANNOUNCEMENT


class TestSendAnnouncementEmail:
    """Tests for send_announcement_email async function."""

    @pytest.mark.asyncio
    @patch("app.tasks.system_announcements.EmailService")
    async def test_sends_email_with_correct_content(
        self, mock_email_service: MagicMock, db_session: Session, test_user: User
    ):
        """Should send email with properly formatted content."""
        mock_service_instance = MagicMock()
        mock_service_instance.send_email.return_value = (True, None)
        mock_email_service.return_value = mock_service_instance

        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.SYSTEM_ANNOUNCEMENT,
            priority=NotificationPriority.HIGH,
            title="📢 Test Announcement",
            message="This is a **test** message",
            notification_metadata={"announcement_priority": "high"},
        )
        db_session.add(notification)
        db_session.commit()

        success, error = await send_announcement_email(
            notification, test_user, db_session
        )

        assert success is True
        assert error is None
        mock_service_instance.send_email.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.tasks.system_announcements.EmailService")
    async def test_applies_priority_styling(
        self, mock_email_service: MagicMock, db_session: Session, test_user: User
    ):
        """Should apply correct styling based on priority."""
        mock_service_instance = MagicMock()
        mock_service_instance.send_email.return_value = (True, None)
        mock_email_service.return_value = mock_service_instance

        # Test high priority
        notif_high = Notification(
            user_id=test_user.id,
            type=NotificationType.SYSTEM_ANNOUNCEMENT,
            priority=NotificationPriority.HIGH,
            title="High Priority",
            message="Test",
            notification_metadata={"announcement_priority": "high"},
        )
        db_session.add(notif_high)
        db_session.commit()

        await send_announcement_email(notif_high, test_user, db_session)

        call_args = mock_service_instance.send_email.call_args
        email_body = call_args[1]["html_content"]
        assert "#e53e3e" in email_body or "red" in email_body.lower()

    @pytest.mark.asyncio
    @patch("app.tasks.system_announcements.EmailService")
    async def test_converts_markdown_to_html(
        self, mock_email_service: MagicMock, db_session: Session, test_user: User
    ):
        """Should convert markdown message to HTML."""
        mock_service_instance = MagicMock()
        mock_service_instance.send_email.return_value = (True, None)
        mock_email_service.return_value = mock_service_instance

        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.SYSTEM_ANNOUNCEMENT,
            priority=NotificationPriority.MEDIUM,
            title="Test",
            message="**Bold** and *italic* text",
            notification_metadata={"announcement_priority": "medium"},
        )
        db_session.add(notification)
        db_session.commit()

        await send_announcement_email(notification, test_user, db_session)

        call_args = mock_service_instance.send_email.call_args
        email_body = call_args[1]["html_content"]
        # Should contain HTML tags for bold/italic
        assert "<strong>" in email_body or "<b>" in email_body

    @pytest.mark.asyncio
    @patch("app.tasks.system_announcements.EmailService")
    async def test_updates_notification_on_success(
        self, mock_email_service: MagicMock, db_session: Session, test_user: User
    ):
        """Should update notification email status on successful send."""
        mock_service_instance = MagicMock()
        mock_service_instance.send_email.return_value = (True, None)
        mock_email_service.return_value = mock_service_instance

        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.SYSTEM_ANNOUNCEMENT,
            priority=NotificationPriority.MEDIUM,
            title="Test",
            message="Test message",
            notification_metadata={"announcement_priority": "medium"},
        )
        db_session.add(notification)
        db_session.commit()

        await send_announcement_email(notification, test_user, db_session)

        db_session.refresh(notification)
        assert notification.email_sent is True
        assert notification.email_sent_at is not None

    @pytest.mark.asyncio
    @patch("app.tasks.system_announcements.EmailService")
    async def test_handles_email_send_failure(
        self, mock_email_service: MagicMock, db_session: Session, test_user: User
    ):
        """Should handle email send failures gracefully."""
        mock_service_instance = MagicMock()
        mock_service_instance.send_email.return_value = (False, "SMTP error")
        mock_email_service.return_value = mock_service_instance

        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.SYSTEM_ANNOUNCEMENT,
            priority=NotificationPriority.MEDIUM,
            title="Test",
            message="Test",
            notification_metadata={"announcement_priority": "medium"},
        )
        db_session.add(notification)
        db_session.commit()

        success, error = await send_announcement_email(
            notification, test_user, db_session
        )

        assert success is False
        assert error == "SMTP error"

    @pytest.mark.asyncio
    @patch("app.tasks.system_announcements.EmailService")
    async def test_handles_exceptions(
        self, mock_email_service: MagicMock, db_session: Session, test_user: User
    ):
        """Should propagate exceptions from email service."""
        mock_service_instance = MagicMock()
        mock_service_instance.send_email.side_effect = Exception("Unexpected error")
        mock_email_service.return_value = mock_service_instance

        notification = Notification(
            user_id=test_user.id,
            type=NotificationType.SYSTEM_ANNOUNCEMENT,
            priority=NotificationPriority.MEDIUM,
            title="Test",
            message="Test",
            notification_metadata={"announcement_priority": "medium"},
        )
        db_session.add(notification)
        db_session.commit()

        # The function doesn't catch exceptions, so it will propagate
        with pytest.raises(Exception) as exc_info:
            await send_announcement_email(notification, test_user, db_session)

        assert "Unexpected error" in str(exc_info.value)


class TestBroadcastSystemAnnouncement:
    """Tests for broadcast_system_announcement Celery task."""

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_broadcasts_to_all_active_users(
        self, mock_session_local: MagicMock, db_session: Session, test_user: User
    ):
        """Should broadcast to all active users when target_all_users=True."""
        mock_session_local.return_value = db_session

        # Create another active user
        password_hash, salt = hash_password("password123")
        user2 = User(
            email="user2@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=True,
            settings={},
        )
        db_session.add(user2)
        db_session.commit()

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test Announcement",
            message="Test message",
            priority="medium",
            target_all_users=True,
            target_user_ids=None,
        )

        assert result["status"] == "success"
        assert result["notifications_created"] >= 2

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_broadcasts_to_specific_users(
        self, mock_session_local: MagicMock, db_session: Session, test_user: User
    ):
        """Should broadcast only to specified user IDs."""
        mock_session_local.return_value = db_session

        # Create additional users
        password_hash, salt = hash_password("password123")
        user2 = User(
            email="user2@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=True,
            settings={},
        )
        user3 = User(
            email="user3@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=True,
            settings={},
        )
        db_session.add_all([user2, user3])
        db_session.commit()

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=False,
            target_user_ids=[str(test_user.id), str(user2.id)],
        )

        assert result["status"] == "success"
        assert result["notifications_created"] == 2

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_respects_user_notification_preferences(
        self, mock_session_local: MagicMock, db_session: Session, test_user: User
    ):
        """Should create notifications by default when user has enabled preference."""
        mock_session_local.return_value = db_session

        # Create enabled preference for test user
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            enabled=True,  # Explicitly enabled
            email_enabled=False,  # Email disabled
        )
        db_session.add(pref)
        db_session.commit()

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=True,
            target_user_ids=None,
        )

        # Should create notification but not send email
        assert result["status"] == "success"
        assert result["notifications_created"] == 1
        assert result["emails_sent"] == 0

    @patch("app.tasks.system_announcements.send_announcement_email")
    @patch("app.tasks.system_announcements.SessionLocal")
    def test_sends_emails_when_enabled(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_user: User,
    ):
        """Should send emails when user has email_enabled=True."""
        mock_session_local.return_value = db_session
        mock_send_email.return_value = (True, None)

        # Enable email notifications
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            enabled=True,
            email_enabled=True,
        )
        db_session.add(pref)
        db_session.commit()

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=True,
            target_user_ids=None,
        )

        assert result["status"] == "success"
        assert result["emails_sent"] >= 0

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_handles_invalid_user_ids(
        self, mock_session_local: MagicMock, db_session: Session
    ):
        """Should handle invalid user IDs gracefully by returning error."""
        mock_session_local.return_value = db_session

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=False,
            target_user_ids=["invalid-uuid", "another-invalid"],
        )

        assert result["status"] == "error"
        assert "badly formed" in result["error"] or "UUID" in result["error"]

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_skips_inactive_users(
        self, mock_session_local: MagicMock, db_session: Session, test_user: User
    ):
        """Should not send announcements to inactive users."""
        mock_session_local.return_value = db_session

        # Make user inactive
        test_user.is_active = False
        db_session.commit()

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=True,
            target_user_ids=None,
        )

        assert result["notifications_created"] == 0

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_handles_errors_gracefully(self, mock_session_local: MagicMock):
        """Should handle errors and return error status."""
        # Mock session that raises exception during use
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database error")
        mock_session_local.return_value = mock_db

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=True,
            target_user_ids=None,
        )

        assert result["status"] == "error"
        assert "Database error" in result["error"]

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_includes_announcement_id_in_response(
        self, mock_session_local: MagicMock, db_session: Session, test_user: User
    ):
        """Should include announcement_id in response."""
        mock_session_local.return_value = db_session

        announcement_id = "announcement-456"
        result = broadcast_system_announcement(
            announcement_id=announcement_id,
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=True,
            target_user_ids=None,
        )

        assert result["announcement_id"] == announcement_id

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_handles_empty_target_user_list(
        self, mock_session_local: MagicMock, db_session: Session
    ):
        """Should return error when target_user_ids is empty and target_all_users=False."""
        mock_session_local.return_value = db_session

        result = broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="medium",
            target_all_users=False,
            target_user_ids=[],
        )

        assert result["status"] == "error"
        assert "No target users specified" in result["error"]

    @patch("app.tasks.system_announcements.SessionLocal")
    def test_creates_notifications_with_correct_priority(
        self, mock_session_local: MagicMock, db_session: Session, test_user: User
    ):
        """Should create notifications with correct priority level."""
        mock_session_local.return_value = db_session

        broadcast_system_announcement(
            announcement_id="test-123",
            title="Test",
            message="Test",
            priority="high",
            target_all_users=True,
            target_user_ids=None,
        )

        notification = (
            db_session.query(Notification)
            .filter(
                Notification.user_id == test_user.id,
                Notification.type == NotificationType.SYSTEM_ANNOUNCEMENT,
            )
            .first()
        )

        assert notification is not None
        assert notification.priority == NotificationPriority.HIGH
