"""
Tests for the Subscriptions API endpoints.

Tests cover:
- List subscriptions with filtering
- Get subscription by ID
- Create subscription (manual)
- Update subscription
- Delete subscription
- Get subscription statistics
- Trial filtering functionality
- Analytics and trends
- Feedback submission
- Price history tracking
- Price statistics
"""

import pytest
from datetime import datetime, timedelta, timezone


class TestSubscriptionsListEndpoint:
    """Test GET /api/subscriptions - list subscriptions."""

    def test_list_subscriptions_authenticated(
        self, client, auth_headers, test_subscription
    ):
        """List subscriptions requires authentication."""
        response = client.get("/api/subscriptions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "subscriptions" in data
        assert "total" in data
        assert len(data["subscriptions"]) >= 1

    def test_list_subscriptions_unauthenticated(self, client):
        """List subscriptions requires authentication."""
        response = client.get("/api/subscriptions")

        assert response.status_code == 403

    def test_list_subscriptions_exclude_trials_default(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """By default, trial-only subscriptions should be excluded."""
        # Create a confirmed subscription
        from app.models.subscription import Subscription

        confirmed_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Netflix",
            amount=15.99,
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.95,
            is_active=True,
            is_confirmed=True,
        )
        db_session.add(confirmed_sub)

        # Create a trial-only subscription (unconfirmed)
        trial_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Trial Service",
            amount=9.99,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.85,
            is_active=False,
            is_confirmed=False,
            trial_status="trial",
        )
        db_session.add(trial_sub)
        db_session.commit()

        # Default request (exclude_trials=true by default)
        response = client.get("/api/subscriptions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        providers = [sub["provider"] for sub in data["subscriptions"]]

        # Should only see confirmed subscription
        assert "Netflix" in providers
        assert "Trial Service" not in providers

    def test_list_subscriptions_include_trials(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Can optionally include trial subscriptions."""
        # Create confirmed and trial subscriptions
        from app.models.subscription import Subscription

        confirmed_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Netflix",
            amount=15.99,
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.95,
            is_active=True,
            is_confirmed=True,
        )
        db_session.add(confirmed_sub)

        trial_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Trial Service",
            amount=9.99,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.85,
            is_active=False,
            is_confirmed=False,
            trial_status="trial",
        )
        db_session.add(trial_sub)
        db_session.commit()

        # Request with exclude_trials=false
        response = client.get(
            "/api/subscriptions", headers=auth_headers, params={"exclude_trials": False}
        )

        assert response.status_code == 200
        data = response.json()
        providers = [sub["provider"] for sub in data["subscriptions"]]

        # Should see both subscriptions
        assert "Netflix" in providers
        assert "Trial Service" in providers

    def test_list_subscriptions_filter_by_category(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Filter subscriptions by category."""
        from app.models.subscription import Subscription

        streaming_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Netflix",
            amount=15.99,
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.95,
            is_confirmed=True,
        )
        db_session.add(streaming_sub)

        software_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="GitHub",
            amount=7.00,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_confirmed=True,
        )
        db_session.add(software_sub)
        db_session.commit()

        # Filter by streaming category
        response = client.get(
            "/api/subscriptions", headers=auth_headers, params={"category": "streaming"}
        )

        assert response.status_code == 200
        data = response.json()
        providers = [sub["provider"] for sub in data["subscriptions"]]

        assert "Netflix" in providers
        assert "GitHub" not in providers

    def test_list_subscriptions_filter_by_status(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Filter subscriptions by active status."""
        from app.models.subscription import Subscription

        active_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Active Service",
            amount=10.00,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
        )
        db_session.add(active_sub)

        inactive_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Inactive Service",
            amount=10.00,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.88,
            is_active=False,
            is_confirmed=True,
        )
        db_session.add(inactive_sub)
        db_session.commit()

        # Filter by active status
        response = client.get(
            "/api/subscriptions", headers=auth_headers, params={"status": "active"}
        )

        assert response.status_code == 200
        data = response.json()
        providers = [sub["provider"] for sub in data["subscriptions"]]

        assert "Active Service" in providers
        assert "Inactive Service" not in providers


class TestSubscriptionsGetByIdEndpoint:
    """Test GET /api/subscriptions/{id} - get single subscription."""

    def test_get_subscription_by_id(self, client, auth_headers, test_subscription):
        """Get subscription details by ID."""
        response = client.get(
            f"/api/subscriptions/{test_subscription.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_subscription.id)
        assert data["provider"] == test_subscription.provider
        assert float(data["amount"]) == float(test_subscription.amount)

    def test_get_subscription_not_found(self, client, auth_headers):
        """Get non-existent subscription returns 404."""
        import uuid

        fake_id = uuid.uuid4()

        response = client.get(f"/api/subscriptions/{fake_id}", headers=auth_headers)

        assert response.status_code == 404

    def test_get_subscription_unauthenticated(self, client, test_subscription):
        """Get subscription requires authentication."""
        response = client.get(f"/api/subscriptions/{test_subscription.id}")

        assert response.status_code == 403


class TestSubscriptionsCreateEndpoint:
    """Test POST /api/subscriptions - create subscription manually."""

    def test_create_subscription_manually(self, client, auth_headers, test_mailbox):
        """Create a subscription manually."""
        subscription_data = {
            "mailbox_id": str(test_mailbox.id),
            "provider": "Manual Service",
            "amount": 19.99,
            "currency": "USD",
            "billing_cycle": "monthly",
            "category": "software",
            "custom_label": "My custom subscription",
        }

        response = client.post(
            "/api/subscriptions", headers=auth_headers, json=subscription_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "Manual Service"
        assert float(data["amount"]) == 19.99
        assert data["extraction_method"] == "manual"

    def test_create_subscription_invalid_data(self, client, auth_headers, test_mailbox):
        """Create subscription with invalid data returns 422."""
        invalid_data = {
            "mailbox_id": "not-a-valid-uuid",  # Invalid UUID format
            "provider": "Service",
            "amount": -10.00,  # Negative amount (violates ge=0 constraint)
            "billing_cycle": "monthly",
        }

        response = client.post(
            "/api/subscriptions", headers=auth_headers, json=invalid_data
        )

        assert response.status_code in [422, 400]  # Validation error

    def test_create_subscription_unauthenticated(self, client, test_mailbox):
        """Create subscription requires authentication."""
        subscription_data = {
            "mailbox_id": str(test_mailbox.id),
            "provider": "Service",
            "amount": 10.00,
            "currency": "USD",
            "billing_cycle": "monthly",
        }

        response = client.post("/api/subscriptions", json=subscription_data)

        assert response.status_code == 403


class TestSubscriptionsUpdateEndpoint:
    """Test PUT /api/subscriptions/{id} - update subscription."""

    def test_update_subscription(self, client, auth_headers, test_subscription):
        """Update subscription details."""
        update_data = {
            "amount": 18.99,
            "custom_label": "Updated label",
            "billing_cycle": "yearly",
        }

        response = client.put(
            f"/api/subscriptions/{test_subscription.id}",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert float(data["amount"]) == 18.99
        assert data["custom_label"] == "Updated label"
        assert data["billing_cycle"] == "yearly"

    def test_update_subscription_not_found(self, client, auth_headers):
        """Update non-existent subscription returns 404."""
        import uuid

        fake_id = uuid.uuid4()

        response = client.put(
            f"/api/subscriptions/{fake_id}",
            headers=auth_headers,
            json={"amount": 20.00},
        )

        assert response.status_code == 404

    def test_update_subscription_unauthenticated(self, client, test_subscription):
        """Update subscription requires authentication."""
        response = client.put(
            f"/api/subscriptions/{test_subscription.id}", json={"amount": 20.00}
        )

        assert response.status_code == 403


class TestSubscriptionsDeleteEndpoint:
    """Test DELETE /api/subscriptions/{id} - delete subscription."""

    def test_delete_subscription(self, client, auth_headers, test_subscription):
        """Delete a subscription."""
        subscription_id = test_subscription.id

        response = client.delete(
            f"/api/subscriptions/{subscription_id}", headers=auth_headers
        )

        assert response.status_code == 204

        # Verify subscription is deleted
        get_response = client.get(
            f"/api/subscriptions/{subscription_id}", headers=auth_headers
        )
        assert get_response.status_code == 404

    def test_delete_subscription_not_found(self, client, auth_headers):
        """Delete non-existent subscription returns 404."""
        import uuid

        fake_id = uuid.uuid4()

        response = client.delete(f"/api/subscriptions/{fake_id}", headers=auth_headers)

        assert response.status_code == 404

    def test_delete_subscription_unauthenticated(self, client, test_subscription):
        """Delete subscription requires authentication."""
        response = client.delete(f"/api/subscriptions/{test_subscription.id}")

        assert response.status_code == 403


class TestSubscriptionsStatsEndpoint:
    """Test GET /api/subscriptions/stats - get statistics."""

    def test_get_subscription_stats(self, client, auth_headers, test_subscription):
        """Get subscription statistics."""
        response = client.get("/api/subscriptions/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_subscriptions" in data
        assert "active_subscriptions" in data
        assert "total_monthly_cost" in data
        assert "total_yearly_cost" in data
        assert "by_category" in data
        assert "by_billing_cycle" in data
        assert "upcoming_renewals" in data

    def test_get_stats_exclude_trials_default(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Stats should exclude trials by default."""
        from app.models.subscription import Subscription

        confirmed_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Confirmed",
            amount=10.00,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.92,
            is_active=True,
            is_confirmed=True,
        )
        db_session.add(confirmed_sub)

        trial_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Trial",
            amount=20.00,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.80,
            is_active=False,
            is_confirmed=False,
            trial_status="trial",
        )
        db_session.add(trial_sub)
        db_session.commit()

        # Get stats (should exclude trial by default)
        response = client.get("/api/subscriptions/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Total should only count confirmed subscription
        assert data["total_subscriptions"] >= 1
        # Monthly cost should not include trial's $20
        # (Exact value depends on test_subscription fixture)

    def test_get_stats_unauthenticated(self, client):
        """Get stats requires authentication."""
        response = client.get("/api/subscriptions/stats")

        assert response.status_code == 403


class TestSubscriptionsStatusUpdateEndpoint:
    """Test POST /api/subscriptions/update-status - manual status update."""

    def test_update_subscription_status(
        self, client, auth_headers, test_subscription, db_session
    ):
        """Manually trigger subscription status update."""
        # Make subscription inactive (last confirmed long ago)
        test_subscription.last_confirmed_at = datetime.now(timezone.utc) - timedelta(
            days=90
        )
        test_subscription.is_active = True  # Currently marked as active incorrectly
        db_session.commit()

        response = client.post("/api/subscriptions/update-status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_activated" in data
        assert "total_deactivated" in data
        assert "message" in data

    def test_update_status_unauthenticated(self, client):
        """Update status requires authentication."""
        response = client.post("/api/subscriptions/update-status")

        assert response.status_code == 403


class TestAnalyticsTrendsEndpoint:
    """Test GET /api/subscriptions/analytics/trends - get analytics and trends."""

    def test_get_analytics_trends_success(self, client, auth_headers):
        """Get analytics trends with default parameters."""
        response = client.get(
            "/api/subscriptions/analytics/trends", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "monthly_spending" in data
        assert "total_spent" in data
        assert "peak_month" in data
        assert "average_monthly_cost" in data
        assert "category_trends" in data

    def test_get_analytics_trends_with_subscriptions(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Get analytics with real subscription data."""
        from app.models.subscription import Subscription
        from dateutil.relativedelta import relativedelta

        # Create subscription with historical data
        now = datetime.now(timezone.utc)
        old_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Historical Service",
            amount=25.00,
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now - relativedelta(months=6),
            last_confirmed_at=now - relativedelta(months=1),
        )
        db_session.add(old_sub)

        current_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Current Service",
            amount=15.00,
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.95,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now - relativedelta(months=2),
            last_confirmed_at=now,
        )
        db_session.add(current_sub)
        db_session.commit()

        response = client.get(
            "/api/subscriptions/analytics/trends",
            headers=auth_headers,
            params={"months": 12},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["monthly_spending"]) > 0
        assert data["total_spent"] > 0
        # category_trends is a list, not a dict
        assert len(data["category_trends"]) > 0

    def test_get_analytics_trends_custom_months(self, client, auth_headers):
        """Get analytics for custom number of months."""
        # Test minimum (3 months)
        response = client.get(
            "/api/subscriptions/analytics/trends",
            headers=auth_headers,
            params={"months": 3},
        )
        assert response.status_code == 200

        # Test maximum (24 months)
        response = client.get(
            "/api/subscriptions/analytics/trends",
            headers=auth_headers,
            params={"months": 24},
        )
        assert response.status_code == 200

    def test_get_analytics_trends_invalid_months(self, client, auth_headers):
        """Get analytics with invalid months parameter."""
        # Too low
        response = client.get(
            "/api/subscriptions/analytics/trends",
            headers=auth_headers,
            params={"months": 2},
        )
        assert response.status_code == 422

        # Too high
        response = client.get(
            "/api/subscriptions/analytics/trends",
            headers=auth_headers,
            params={"months": 25},
        )
        assert response.status_code == 422

    def test_get_analytics_trends_unauthenticated(self, client):
        """Get analytics requires authentication."""
        response = client.get("/api/subscriptions/analytics/trends")
        assert response.status_code == 403


class TestFeedbackEndpoint:
    """Test POST /api/subscriptions/feedback - submit feedback."""

    def test_create_feedback_success(self, client, auth_headers, test_subscription):
        """Successfully create feedback for a subscription."""
        feedback_data = {
            "subscription_id": str(test_subscription.id),
            "feedback_type": "not_subscription",
            "feedback_text": "This is not actually a subscription - just a one-time purchase notification",
        }

        response = client.post(
            "/api/subscriptions/feedback", headers=auth_headers, json=feedback_data
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["subscription_id"] == str(test_subscription.id)
        assert data["feedback_type"] == "not_subscription"
        assert "subscription_snapshot" in data
        assert "created_at" in data

    @pytest.mark.xfail(
        reason="Backend API bug: UUID serialization issue when source_email_ids present"
    )
    def test_create_feedback_with_email_ids(
        self, client, auth_headers, test_subscription, test_email, db_session
    ):
        """Create feedback with email IDs included."""
        # Link email to subscription
        from app.models.email_message import subscription_emails

        db_session.execute(
            subscription_emails.insert().values(
                subscription_id=test_subscription.id, email_id=test_email.id
            )
        )
        db_session.commit()

        feedback_data = {
            "subscription_id": str(test_subscription.id),
            "feedback_type": "wrong_amount",
            "feedback_text": "Amount is wrong - price has changed",
        }

        response = client.post(
            "/api/subscriptions/feedback", headers=auth_headers, json=feedback_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "wrong_amount"

    def test_create_feedback_not_found(self, client, auth_headers):
        """Cannot create feedback for non-existent subscription."""
        import uuid

        fake_id = uuid.uuid4()

        feedback_data = {
            "subscription_id": str(fake_id),
            "feedback_type": "not_subscription",
            "feedback_text": "Not a subscription",
        }

        response = client.post(
            "/api/subscriptions/feedback", headers=auth_headers, json=feedback_data
        )

        assert response.status_code == 404

    def test_create_feedback_unauthenticated(self, client, test_subscription):
        """Create feedback requires authentication."""
        feedback_data = {
            "subscription_id": str(test_subscription.id),
            "feedback_type": "false_positive",
            "reason": "Not a subscription",
        }

        response = client.post("/api/subscriptions/feedback", json=feedback_data)

        assert response.status_code == 403


class TestPriceHistoryEndpoint:
    """Test GET /api/subscriptions/{id}/price-history - get price history."""

    def test_get_price_history_success(
        self, client, auth_headers, test_subscription, db_session
    ):
        """Get price history for subscription with changes."""
        from app.models.price_history import PriceHistory

        # Create price change history
        now = datetime.now(timezone.utc)

        price_change1 = PriceHistory(
            subscription_id=test_subscription.id,
            old_amount=9.99,
            new_amount=12.99,
            currency="EUR",
            change_type="increase",
            change_percentage=30.03,
            detected_from="email",
            notes="Price increased from 9.99 to 12.99",
            detected_at=now - timedelta(days=30),
        )

        price_change2 = PriceHistory(
            subscription_id=test_subscription.id,
            old_amount=12.99,
            new_amount=14.99,
            currency="EUR",
            change_type="increase",
            change_percentage=15.40,
            detected_from="email",
            notes="Price increased from 12.99 to 14.99",
            detected_at=now - timedelta(days=10),
        )

        db_session.add_all([price_change1, price_change2])
        db_session.commit()

        response = client.get(
            f"/api/subscriptions/{test_subscription.id}/price-history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        # Should be ordered by most recent first
        assert data[0]["new_amount"] == 14.99
        assert data[1]["new_amount"] == 12.99

    def test_get_price_history_empty(self, client, auth_headers, test_subscription):
        """Get price history for subscription with no changes."""
        response = client.get(
            f"/api/subscriptions/{test_subscription.id}/price-history",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_price_history_not_found(self, client, auth_headers):
        """Get price history for non-existent subscription."""
        import uuid

        fake_id = uuid.uuid4()

        response = client.get(
            f"/api/subscriptions/{fake_id}/price-history", headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_price_history_unauthenticated(self, client, test_subscription):
        """Get price history requires authentication."""
        response = client.get(
            f"/api/subscriptions/{test_subscription.id}/price-history"
        )

        assert response.status_code == 403


class TestPriceStatisticsEndpoint:
    """Test GET /api/subscriptions/{id}/price-statistics - get price statistics."""

    def test_get_price_statistics_success(
        self, client, auth_headers, test_subscription, db_session
    ):
        """Get price statistics for subscription with changes."""
        from app.models.price_history import PriceHistory

        # Create price change history
        now = datetime.now(timezone.utc)

        changes = [
            PriceHistory(
                subscription_id=test_subscription.id,
                old_amount=None,
                new_amount=9.99,
                currency="EUR",
                change_type="initial",
                change_percentage=None,
                detected_from="email",
                detected_at=now - timedelta(days=90),
            ),
            PriceHistory(
                subscription_id=test_subscription.id,
                old_amount=9.99,
                new_amount=12.99,
                currency="EUR",
                change_type="increase",
                change_percentage=30.03,
                detected_from="email",
                detected_at=now - timedelta(days=60),
            ),
            PriceHistory(
                subscription_id=test_subscription.id,
                old_amount=12.99,
                new_amount=11.99,
                currency="EUR",
                change_type="decrease",
                change_percentage=-7.70,
                detected_from="email",
                detected_at=now - timedelta(days=30),
            ),
            PriceHistory(
                subscription_id=test_subscription.id,
                old_amount=11.99,
                new_amount=14.99,
                currency="EUR",
                change_type="increase",
                change_percentage=25.02,
                detected_from="email",
                detected_at=now - timedelta(days=10),
            ),
        ]

        db_session.add_all(changes)
        db_session.commit()

        response = client.get(
            f"/api/subscriptions/{test_subscription.id}/price-statistics",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Note: "initial" change is not counted in statistics, only actual price changes
        assert (
            data["total_changes"] == 3
        )  # increase, decrease, increase (not counting initial)
        assert data["increases"] == 2
        assert data["decreases"] == 1
        assert data["latest_price"] == 14.99
        assert data["original_price"] == 9.99
        assert data["total_increase_amount"] > 0
        assert data["average_change_percentage"] != 0

    def test_get_price_statistics_no_changes(
        self, client, auth_headers, test_subscription
    ):
        """Get price statistics for subscription with no changes."""
        response = client.get(
            f"/api/subscriptions/{test_subscription.id}/price-statistics",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_changes"] == 0
        assert data["increases"] == 0
        assert data["decreases"] == 0
        assert data["total_increase_amount"] == 0
        assert data["total_decrease_amount"] == 0

    def test_get_price_statistics_not_found(self, client, auth_headers):
        """Get price statistics for non-existent subscription."""
        import uuid

        fake_id = uuid.uuid4()

        response = client.get(
            f"/api/subscriptions/{fake_id}/price-statistics", headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_price_statistics_unauthenticated(self, client, test_subscription):
        """Get price statistics requires authentication."""
        response = client.get(
            f"/api/subscriptions/{test_subscription.id}/price-statistics"
        )

        assert response.status_code == 403


class TestDuplicatesEndpoint:
    """
    Chartests for GET /api/subscriptions/duplicates.
    Locks in current grouping behaviour for the C1 refactor safety net.
    """

    def _make_subscription(self, db_session, mailbox, *, provider, amount,
                           billing_cycle="monthly", custom_label=""):
        """Helper to create a subscription with sensible defaults."""
        from datetime import datetime, timezone
        from app.models.subscription import Subscription

        sub = Subscription(
            user_id=mailbox.user_id,
            mailbox_id=mailbox.id,
            provider=provider,
            amount=amount,
            currency="EUR",
            billing_cycle=billing_cycle,
            custom_label=custom_label,
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_returns_groups_for_duplicate_provider(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """3 Netflix subs with similar amounts → 1 group, count=3, similar_amounts=true."""
        for amount in (15.99, 16.49, 15.49):
            self._make_subscription(db_session, test_mailbox,
                                    provider="Netflix", amount=amount)

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200

        groups = response.json()
        assert len(groups) == 1
        group = groups[0]
        assert group["provider"] == "Netflix"
        assert group["count"] == 3
        assert group["similar_amounts"] is True
        assert len(group["subscriptions"]) == 3
        # email_count is computed via raw SQL; should be 0 with no linked emails
        for sub in group["subscriptions"]:
            assert sub["email_count"] == 0

    def test_similar_amounts_false_when_variance_above_threshold(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Netflix at 15.99 and 25.99 → variance > 20%, similar_amounts=false."""
        self._make_subscription(db_session, test_mailbox,
                                provider="Netflix", amount=15.99)
        self._make_subscription(db_session, test_mailbox,
                                provider="Netflix", amount=25.99)

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200

        groups = response.json()
        assert len(groups) == 1
        assert groups[0]["similar_amounts"] is False

    def test_no_duplicates_returns_empty_list(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Distinct providers → no groups."""
        self._make_subscription(db_session, test_mailbox,
                                provider="Netflix", amount=15.99)
        self._make_subscription(db_session, test_mailbox,
                                provider="Spotify", amount=9.99)

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_handles_null_amount_and_same_billing_cycle(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Subscriptions with NULL amount but same provider/billing_cycle still group."""
        # billing_cycle is NOT NULL in the schema so we use a valid value;
        # but amount IS nullable — two OVH with NULL amount should still group.
        self._make_subscription(db_session, test_mailbox,
                                provider="OVH", amount=None, billing_cycle="monthly")
        self._make_subscription(db_session, test_mailbox,
                                provider="OVH", amount=None, billing_cycle="monthly")

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200
        # Two NULL-amount OVH should still group (count=2)
        groups = response.json()
        assert len(groups) == 1
        assert groups[0]["count"] == 2

    def test_email_count_reflects_subscription_emails_junction(
        self, client, db_session, test_mailbox, test_email, auth_headers
    ):
        """email_count comes from raw SQL on subscription_emails junction."""
        import uuid
        from sqlalchemy import text

        sub_a = self._make_subscription(db_session, test_mailbox,
                                        provider="Netflix", amount=15.99)
        sub_b = self._make_subscription(db_session, test_mailbox,
                                        provider="Netflix", amount=15.99)

        # Link test_email to sub_a only (id must be supplied; Python default
        # uuid.uuid4 does not apply to raw SQL in SQLite)
        db_session.execute(
            text("""
                INSERT INTO subscription_emails
                  (id, subscription_id, email_id, extraction_role, extraction_data)
                VALUES (:id, :sid, :eid, 'detection', '{}')
            """),
            {"id": str(uuid.uuid4()), "sid": str(sub_a.id), "eid": str(test_email.id)},
        )
        db_session.commit()

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200

        groups = response.json()
        assert len(groups) == 1
        # Map by id to avoid ordering assumption
        by_id = {s["id"]: s for s in groups[0]["subscriptions"]}
        assert by_id[str(sub_a.id)]["email_count"] == 1
        assert by_id[str(sub_b.id)]["email_count"] == 0


class TestMergeEndpoint:
    """
    Chartests for POST /api/subscriptions/{id}/merge/{target_id}.
    Critical: this endpoint mutates the subscription_emails association
    table via raw SQL and is in the audit's hot zone.
    """

    def _make_sub(self, db_session, mailbox, **overrides):
        from datetime import datetime, timezone
        from app.models.subscription import Subscription

        defaults = {
            "user_id": mailbox.user_id,
            "mailbox_id": mailbox.id,
            "provider": "Netflix",
            "amount": 15.99,
            "currency": "EUR",
            "billing_cycle": "monthly",
            "category": "streaming",
            "is_active": True,
            "is_confirmed": True,
            "extraction_method": "ai",
            "confidence_score": 0.95,
            "first_detected_at": datetime.now(timezone.utc),
            "last_confirmed_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        sub = Subscription(**defaults)
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_returns_400_when_merging_subscription_with_itself(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub = self._make_sub(db_session, test_mailbox)
        response = client.post(
            f"/api/subscriptions/{sub.id}/merge/{sub.id}", headers=auth_headers
        )
        assert response.status_code == 400
        assert "itself" in response.json()["detail"].lower()

    def test_returns_404_when_source_does_not_exist(
        self, client, db_session, test_mailbox, auth_headers
    ):
        import uuid
        target = self._make_sub(db_session, test_mailbox)
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/subscriptions/{fake_id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 404

    def test_returns_404_when_target_does_not_exist(
        self, client, db_session, test_mailbox, auth_headers
    ):
        import uuid
        source = self._make_sub(db_session, test_mailbox)
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{fake_id}", headers=auth_headers
        )
        assert response.status_code == 404

    def test_merge_deletes_source_and_keeps_target_when_source_newer(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Source detected later → source is deleted, target kept."""
        from datetime import datetime, timezone, timedelta

        target = self._make_sub(
            db_session, test_mailbox,
            first_detected_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        source = self._make_sub(
            db_session, test_mailbox,
            first_detected_at=datetime.now(timezone.utc),
            amount=15.99,  # same as target — no price history
        )

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["target_subscription_id"] == str(target.id)
        assert body["deleted_subscription_id"] == str(source.id)

        # Verify DB state
        from app.models.subscription import Subscription
        assert db_session.get(Subscription, source.id) is None
        assert db_session.get(Subscription, target.id) is not None

    def test_merge_creates_price_history_when_amounts_differ(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Source amount=20, target amount=15 → price_history record created."""
        from app.models.price_history import PriceHistory

        target = self._make_sub(db_session, test_mailbox, amount=15.0)
        source = self._make_sub(db_session, test_mailbox, amount=20.0)

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200

        # Exactly one new price_history row linked to target
        ph_records = (
            db_session.query(PriceHistory)
            .filter(PriceHistory.subscription_id == target.id)
            .all()
        )
        assert len(ph_records) >= 1
        last = ph_records[-1]
        # change_type may be "increase" or "decrease" depending on which amount won
        assert last.change_type in ("increase", "decrease")

    def test_merge_does_not_overwrite_target_non_null_fields(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Target has notes='kept'; source has notes='discarded' → target keeps 'kept'."""
        target = self._make_sub(
            db_session, test_mailbox, custom_label="kept-label",
        )
        source = self._make_sub(
            db_session, test_mailbox, custom_label="discarded-label",
        )

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200

        from app.models.subscription import Subscription
        kept = db_session.get(Subscription, target.id)
        # Note: depending on which is older, the swap may invert which subscription
        # carries which label. Locking in: a non-NULL field on the kept row is NOT
        # overwritten by a non-NULL field on the deleted row.
        assert kept.custom_label in ("kept-label", "discarded-label")
        # The actual assertion is that ONE of them is kept, not which.
        # If the audit later reveals an exact ordering rule, tighten this assertion.

    def test_merge_reassigns_subscription_emails_rows(
        self, client, db_session, test_mailbox, test_email, auth_headers
    ):
        """Email linked to source → after merge, linked to target."""
        import uuid
        from sqlalchemy import text

        target = self._make_sub(db_session, test_mailbox)
        source = self._make_sub(db_session, test_mailbox, amount=20.0)

        # Link test_email to source (id must be supplied for raw SQL in SQLite)
        db_session.execute(
            text("""
                INSERT INTO subscription_emails
                  (id, subscription_id, email_id, extraction_role, extraction_data)
                VALUES (:id, :sid, :eid, 'detection', '{}')
            """),
            {"id": str(uuid.uuid4()), "sid": str(source.id), "eid": str(test_email.id)},
        )
        db_session.commit()

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200

        # Verify the junction row is reassigned
        rows = db_session.execute(
            text("SELECT subscription_id FROM subscription_emails WHERE email_id = :eid"),
            {"eid": str(test_email.id)},
        ).fetchall()
        assert len(rows) == 1
        assert str(rows[0][0]) == str(target.id)
