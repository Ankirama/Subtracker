"""
Tests for Notifications API endpoints.

Tests cover:
- List notifications (pagination, filtering)
- Unread count
- Mark read (single, all)
- Delete notification
- Notification preferences
- Upcoming renewals
- Summary preview
"""

import pytest
from datetime import datetime, timezone, timedelta, date

from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
)


class TestListNotifications:
    """Test GET /api/notifications/ - list notifications."""

    def test_list_notifications_empty(self, client, auth_headers):
        """List notifications when user has none."""
        response = client.get("/api/notifications/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["unread_count"] == 0
        assert len(data["notifications"]) == 0
        assert data["has_more"] is False

    def test_list_notifications_with_data(
        self, client, auth_headers, db_session, test_user
    ):
        """List notifications returns user's notifications."""
        # Create test notifications
        notif1 = Notification(
            user_id=test_user.id,
            type=NotificationType.RENEWAL_REMINDER,
            title="Renewal Upcoming",
            message="Your Netflix subscription renews tomorrow",
            is_read=False,
        )
        notif2 = Notification(
            user_id=test_user.id,
            type=NotificationType.PRICE_CHANGE,
            title="Price Increase",
            message="Spotify price increased",
            is_read=True,
        )
        db_session.add_all([notif1, notif2])
        db_session.commit()

        response = client.get("/api/notifications/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert data["unread_count"] == 1
        assert len(data["notifications"]) == 2

    def test_list_notifications_unread_only(
        self, client, auth_headers, db_session, test_user
    ):
        """Filter notifications to show only unread."""
        # Create mix of read and unread
        unread = Notification(
            user_id=test_user.id,
            type=NotificationType.RENEWAL_REMINDER,
            title="Unread",
            message="Unread message",
            is_read=False,
        )
        read = Notification(
            user_id=test_user.id,
            type=NotificationType.PRICE_CHANGE,
            title="Read",
            message="Read message",
            is_read=True,
        )
        db_session.add_all([unread, read])
        db_session.commit()

        response = client.get(
            "/api/notifications/", headers=auth_headers, params={"unread_only": True}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["is_read"] is False

    def test_list_notifications_filter_by_type(
        self, client, auth_headers, db_session, test_user
    ):
        """Filter notifications by type."""
        renewal = Notification(
            user_id=test_user.id,
            type=NotificationType.RENEWAL_REMINDER,
            title="Renewal",
            message="Renewal reminder",
            is_read=False,
        )
        price = Notification(
            user_id=test_user.id,
            type=NotificationType.PRICE_CHANGE,
            title="Price",
            message="Price change",
            is_read=False,
        )
        db_session.add_all([renewal, price])
        db_session.commit()

        response = client.get(
            "/api/notifications/",
            headers=auth_headers,
            params={"notification_type": "renewal_reminder"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["notifications"][0]["type"] == "renewal_reminder"

    def test_list_notifications_pagination(
        self, client, auth_headers, db_session, test_user
    ):
        """Pagination works correctly."""
        # Create 25 notifications
        for i in range(25):
            notif = Notification(
                user_id=test_user.id,
                type=NotificationType.RENEWAL_REMINDER,
                title=f"Notification {i}",
                message=f"Message {i}",
                is_read=False,
            )
            db_session.add(notif)
        db_session.commit()

        # Get first page (default 20 per page)
        response = client.get(
            "/api/notifications/",
            headers=auth_headers,
            params={"page": 1, "page_size": 20},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 25
        assert len(data["notifications"]) == 20
        assert data["has_more"] is True
        assert data["page"] == 1
        assert data["page_size"] == 20

        # Get second page
        response2 = client.get(
            "/api/notifications/",
            headers=auth_headers,
            params={"page": 2, "page_size": 20},
        )

        data2 = response2.json()
        assert len(data2["notifications"]) == 5
        assert data2["has_more"] is False


class TestUnreadCount:
    """Test GET /api/notifications/unread-count - get unread count."""

    def test_unread_count_zero(self, client, auth_headers):
        """Unread count is zero when no notifications."""
        response = client.get("/api/notifications/unread-count", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["unread_count"] == 0

    def test_unread_count_with_notifications(
        self, client, auth_headers, db_session, test_user
    ):
        """Unread count returns correct number."""
        # Create 3 unread, 2 read
        for i in range(3):
            db_session.add(
                Notification(
                    user_id=test_user.id,
                    type=NotificationType.RENEWAL_REMINDER,
                    title="Unread",
                    message=f"Unread {i}",
                    is_read=False,
                )
            )
        for i in range(2):
            db_session.add(
                Notification(
                    user_id=test_user.id,
                    type=NotificationType.PRICE_CHANGE,
                    title="Read",
                    message=f"Read {i}",
                    is_read=True,
                )
            )
        db_session.commit()

        response = client.get("/api/notifications/unread-count", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["unread_count"] == 3


class TestMarkNotificationsRead:
    """Test POST /api/notifications/mark-read - mark notifications as read."""

    def test_mark_notifications_read_success(
        self, client, auth_headers, db_session, test_user
    ):
        """Successfully mark specific notifications as read."""
        notif1 = Notification(
            user_id=test_user.id,
            type=NotificationType.RENEWAL_REMINDER,
            title="Test 1",
            message="Message 1",
            is_read=False,
        )
        notif2 = Notification(
            user_id=test_user.id,
            type=NotificationType.RENEWAL_REMINDER,
            title="Test 2",
            message="Message 2",
            is_read=False,
        )
        db_session.add_all([notif1, notif2])
        db_session.commit()
        db_session.refresh(notif1)
        db_session.refresh(notif2)

        response = client.post(
            "/api/notifications/mark-read",
            headers=auth_headers,
            json={"notification_ids": [str(notif1.id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["marked_read"] == 1

        # Verify in database
        db_session.refresh(notif1)
        db_session.refresh(notif2)
        assert notif1.is_read is True
        assert notif2.is_read is False


class TestMarkAllNotificationsRead:
    """Test POST /api/notifications/mark-all-read - mark all as read."""

    def test_mark_all_notifications_read(
        self, client, auth_headers, db_session, test_user
    ):
        """Successfully mark all unread notifications as read."""
        # Create 3 unread notifications
        for i in range(3):
            db_session.add(
                Notification(
                    user_id=test_user.id,
                    type=NotificationType.RENEWAL_REMINDER,
                    title=f"Test {i}",
                    message=f"Message {i}",
                    is_read=False,
                )
            )
        db_session.commit()

        response = client.post("/api/notifications/mark-all-read", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["marked_read"] == 3

        # Verify all are now read
        unread_count = (
            db_session.query(Notification)
            .filter(Notification.user_id == test_user.id, Notification.is_read == False)
            .count()
        )
        assert unread_count == 0


class TestDeleteNotification:
    """Test DELETE /api/notifications/{id} - delete notification."""

    def test_delete_notification_success(
        self, client, auth_headers, db_session, test_user
    ):
        """Successfully delete a notification."""
        notif = Notification(
            user_id=test_user.id,
            type=NotificationType.RENEWAL_REMINDER,
            title="Delete Me",
            message="This should be deleted",
            is_read=False,
        )
        db_session.add(notif)
        db_session.commit()
        db_session.refresh(notif)

        notif_id = notif.id

        response = client.delete(f"/api/notifications/{notif_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify deleted
        deleted = (
            db_session.query(Notification).filter(Notification.id == notif_id).first()
        )
        assert deleted is None

    def test_delete_notification_not_found(self, client, auth_headers):
        """Cannot delete non-existent notification."""
        from uuid import uuid4

        fake_id = uuid4()

        response = client.delete(f"/api/notifications/{fake_id}", headers=auth_headers)

        assert response.status_code == 404


class TestNotificationPreferences:
    """Test notification preference endpoints."""

    def test_get_notification_preferences(self, client, auth_headers):
        """Get notification preferences (creates defaults if needed)."""
        response = client.get("/api/notifications/preferences", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "preferences" in data
        # Should have preferences for all notification types
        assert len(data["preferences"]) > 0

    def test_update_notification_preference(self, client, auth_headers):
        """Update notification preference for a specific type."""
        update_data = {"enabled": False, "email_enabled": False}

        response = client.put(
            "/api/notifications/preferences/renewal_reminder",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["notification_type"] == "renewal_reminder"
        assert data["enabled"] is False
        assert data["email_enabled"] is False


class TestUpcomingRenewals:
    """Test GET /api/notifications/upcoming-renewals."""

    def test_upcoming_renewals_empty(self, client, auth_headers):
        """No upcoming renewals when user has no active subscriptions."""
        response = client.get(
            "/api/notifications/upcoming-renewals", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_upcoming_renewals_with_subscriptions(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Returns upcoming renewals within specified days."""
        from app.models.subscription import Subscription

        # Create subscription renewing in 15 days
        future_renewal = date.today() + timedelta(days=15)
        sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="TestService",
            amount=10.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            next_billing_date=future_renewal,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()

        response = client.get(
            "/api/notifications/upcoming-renewals",
            headers=auth_headers,
            params={"days_ahead": 30},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["provider"] == "TestService"
        assert data[0]["days_until_renewal"] == 15


class TestSummaryPreview:
    """Test GET /api/notifications/summary/preview."""

    def test_summary_preview_weekly(self, client, auth_headers):
        """Preview weekly summary."""
        response = client.get(
            "/api/notifications/summary/preview",
            headers=auth_headers,
            params={"period_type": "weekly"},
        )

        assert response.status_code == 200
        # Should return summary data structure
        data = response.json()
        assert data is not None

    def test_summary_preview_monthly(self, client, auth_headers):
        """Preview monthly summary."""
        response = client.get(
            "/api/notifications/summary/preview",
            headers=auth_headers,
            params={"period_type": "monthly"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data is not None
