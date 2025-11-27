"""Comprehensive tests for summary_service"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock
from decimal import Decimal

from app.services.summary_service import SummaryService
from app.models.user import User
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription


@pytest.fixture
def test_mailbox(db_session: Session, test_user: User) -> Mailbox:
    """Create a test mailbox"""
    mailbox = Mailbox(
        id=uuid4(),
        user_id=test_user.id,
        email_address="test@example.com",
        provider_type="gmail",
        encrypted_credentials="test_encrypted_credentials",
        is_active=True,
    )
    db_session.add(mailbox)
    db_session.commit()
    db_session.refresh(mailbox)
    return mailbox


@pytest.fixture
def test_subscriptions(db_session: Session, test_user: User, test_mailbox: Mailbox):
    """Create test subscriptions with various states"""
    now = datetime.now()

    # Active subscription - Netflix (detected 90 days ago)
    netflix = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        mailbox_id=test_mailbox.id,
        provider="Netflix",
        amount=Decimal("15.99"),
        currency="USD",
        billing_cycle="monthly",
        category="streaming",
        is_active=True,
        first_detected_at=now - timedelta(days=90),
    )

    # Active subscription - Spotify (detected 60 days ago)
    spotify = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        mailbox_id=test_mailbox.id,
        provider="Spotify",
        amount=Decimal("9.99"),
        currency="USD",
        billing_cycle="monthly",
        category="music",
        is_active=True,
        first_detected_at=now - timedelta(days=60),
    )

    # New subscription (detected 3 days ago - within last 7 days)
    gym = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        mailbox_id=test_mailbox.id,
        provider="Gym Membership",
        amount=Decimal("50.00"),
        currency="USD",
        billing_cycle="monthly",
        category="fitness",
        is_active=True,
        first_detected_at=now - timedelta(days=3),
    )

    # Recently cancelled subscription (last confirmed 5 days ago, now inactive)
    old_service = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        mailbox_id=test_mailbox.id,
        provider="Old Service",
        amount=Decimal("19.99"),
        currency="USD",
        billing_cycle="monthly",
        category="tools",
        is_active=False,
        first_detected_at=now - timedelta(days=120),
        last_confirmed_at=now - timedelta(days=5),
    )

    # Yearly subscription - Adobe (detected 200 days ago)
    adobe = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        mailbox_id=test_mailbox.id,
        provider="Adobe",
        amount=Decimal("599.99"),
        currency="USD",
        billing_cycle="yearly",
        category="software",
        is_active=True,
        first_detected_at=now - timedelta(days=200),
    )

    subscriptions = [netflix, spotify, gym, old_service, adobe]
    for sub in subscriptions:
        db_session.add(sub)
    db_session.commit()

    return {
        "netflix": netflix,
        "spotify": spotify,
        "gym": gym,
        "old_service": old_service,
        "adobe": adobe,
    }


class TestGenerateWeeklySummary:
    """Tests for generate_weekly_summary method"""

    @patch("app.services.summary_service.AIOptimizer.analyze_subscriptions")
    def test_generates_weekly_summary_with_subscriptions(
        self,
        mock_ai_analyze: MagicMock,
        db_session: Session,
        test_user: User,
        test_mailbox: Mailbox,
        test_subscriptions,
    ):
        """Should generate comprehensive weekly summary"""
        # Mock AI optimizer
        mock_ai_analyze.return_value = {
            "recommendations": ["Test recommendation"],
            "insights": ["Test insight"],
            "potential_savings": 50.0,
        }

        result = SummaryService.generate_weekly_summary(db_session, test_user)

        # Verify basic structure
        assert result["period_type"] == "weekly"
        assert "start_date" in result
        assert "end_date" in result

        # Verify overview (flat structure, not nested)
        assert result["total_subscriptions"] == 4  # 4 active
        assert result["total_monthly_cost"] > 0

        # Verify changes (gym added in last 3 days, old_service cancelled in last 5 days)
        assert len(result["new_subscriptions"]) == 1
        assert result["new_subscriptions"][0]["provider"] == "Gym Membership"
        assert len(result["cancelled_subscriptions"]) == 1
        assert result["cancelled_subscriptions"][0]["provider"] == "Old Service"

        # Verify analysis
        assert len(result["top_subscriptions"]) > 0

        # Verify AI integration
        mock_ai_analyze.assert_called_once()
        assert result["ai_recommendations"] == ["Test recommendation"]
        assert result["ai_insights"] == ["Test insight"]
        assert result["potential_savings"] == 50.0

    @patch("app.services.summary_service.AIOptimizer.analyze_subscriptions")
    def test_handles_ai_optimizer_error_gracefully(
        self,
        mock_ai_analyze: MagicMock,
        db_session: Session,
        test_user: User,
        test_mailbox: Mailbox,
        test_subscriptions,
    ):
        """Should handle AI optimizer errors without failing"""
        mock_ai_analyze.side_effect = Exception("AI service down")

        result = SummaryService.generate_weekly_summary(db_session, test_user)

        # Should still return summary without AI data
        assert result["period_type"] == "weekly"
        assert result["total_subscriptions"] == 4
        assert result["ai_recommendations"] == []
        assert result["ai_insights"] == []
        assert result["potential_savings"] == 0.0

    def test_returns_empty_summary_for_no_subscriptions(
        self, db_session: Session, test_user: User
    ):
        """Should return empty summary when user has no subscriptions"""
        result = SummaryService.generate_weekly_summary(db_session, test_user)

        assert result["period_type"] == "weekly"
        assert result["total_subscriptions"] == 0
        assert result["total_monthly_cost"] == 0
        assert result["new_subscriptions"] == []
        assert result["cancelled_subscriptions"] == []


class TestGenerateMonthlySummary:
    """Tests for generate_monthly_summary method"""

    @patch("app.services.summary_service.AIOptimizer.analyze_subscriptions")
    def test_generates_monthly_summary_with_subscriptions(
        self,
        mock_ai_analyze: MagicMock,
        db_session: Session,
        test_user: User,
        test_mailbox: Mailbox,
        test_subscriptions,
    ):
        """Should generate comprehensive monthly summary"""
        mock_ai_analyze.return_value = {
            "recommendations": ["Test recommendation"],
            "insights": ["Test insight"],
            "potential_savings": 100.0,
        }

        result = SummaryService.generate_monthly_summary(db_session, test_user)

        # Verify period type
        assert result["period_type"] == "monthly"

        # Verify overview
        assert result["total_subscriptions"] == 4  # 4 active
        assert result["total_monthly_cost"] > 0

        # Monthly should capture more changes than weekly
        assert len(result["new_subscriptions"]) >= 1

        # Verify AI integration
        mock_ai_analyze.assert_called_once()
        assert result["potential_savings"] == 100.0


class TestGetMonthlyCost:
    """Tests for _get_monthly_cost method"""

    def test_converts_monthly_subscription(self, db_session: Session, test_user: User):
        """Should return amount as-is for monthly subscriptions"""
        sub = Subscription(
            user_id=test_user.id, amount=Decimal("15.99"), billing_cycle="monthly"
        )

        cost = SummaryService._get_monthly_cost(sub)
        assert cost == 15.99

    def test_converts_yearly_subscription(self, db_session: Session, test_user: User):
        """Should divide by 12 for yearly subscriptions"""
        sub = Subscription(
            user_id=test_user.id, amount=Decimal("120.00"), billing_cycle="yearly"
        )

        cost = SummaryService._get_monthly_cost(sub)
        assert cost == pytest.approx(10.0, rel=0.01)

    def test_converts_weekly_subscription(self, db_session: Session, test_user: User):
        """Should multiply by 4.33 for weekly subscriptions"""
        sub = Subscription(
            user_id=test_user.id, amount=Decimal("10.00"), billing_cycle="weekly"
        )

        cost = SummaryService._get_monthly_cost(sub)
        assert cost == pytest.approx(43.3, rel=0.01)

    def test_converts_quarterly_subscription(
        self, db_session: Session, test_user: User
    ):
        """Should divide by 3 for quarterly subscriptions"""
        sub = Subscription(
            user_id=test_user.id, amount=Decimal("90.00"), billing_cycle="quarterly"
        )

        cost = SummaryService._get_monthly_cost(sub)
        assert cost == pytest.approx(30.0, rel=0.01)

    def test_converts_biannual_subscription(self, db_session: Session, test_user: User):
        """Should divide by 6 for biannual subscriptions"""
        sub = Subscription(
            user_id=test_user.id, amount=Decimal("180.00"), billing_cycle="biannual"
        )

        cost = SummaryService._get_monthly_cost(sub)
        assert cost == pytest.approx(30.0, rel=0.01)

    def test_returns_zero_for_no_amount(self, db_session: Session, test_user: User):
        """Should return 0 for subscriptions with no amount"""
        sub = Subscription(user_id=test_user.id, amount=None, billing_cycle="monthly")

        cost = SummaryService._get_monthly_cost(sub)
        assert cost == 0.0

    def test_returns_zero_for_unknown_cycle(self, db_session: Session, test_user: User):
        """Should return 0 for unknown billing cycles"""
        sub = Subscription(
            user_id=test_user.id, amount=Decimal("25.00"), billing_cycle="unknown_cycle"
        )

        cost = SummaryService._get_monthly_cost(sub)
        assert cost == 0.0


class TestGenerateInsights:
    """Tests for _generate_insights method"""

    def test_generates_new_subscription_insight(
        self, db_session: Session, test_user: User
    ):
        """Should generate insight for new subscriptions"""
        sub1 = Subscription(
            user_id=test_user.id,
            provider="Netflix",
            amount=Decimal("15.99"),
            billing_cycle="monthly",
        )
        sub2 = Subscription(
            user_id=test_user.id,
            provider="Spotify",
            amount=Decimal("9.99"),
            billing_cycle="monthly",
        )

        active_subs = []
        new_subs = [sub1, sub2]
        cancelled_subs = []

        insights = SummaryService._generate_insights(
            active_subs, new_subs, cancelled_subs, 50.0, {}
        )

        assert any("2 net new subscriptions" in insight for insight in insights)

    def test_generates_spending_insight(self, db_session: Session, test_user: User):
        """Should generate insight about total spending"""
        sub1 = Subscription(
            user_id=test_user.id,
            provider="Netflix",
            amount=Decimal("15.99"),
            billing_cycle="monthly",
        )
        active_subs = [sub1]
        new_subs = []
        cancelled_subs = []

        insights = SummaryService._generate_insights(
            active_subs, new_subs, cancelled_subs, 150.99, {}
        )

        assert any("150.99" in insight for insight in insights)

    def test_generates_category_insight(self, db_session: Session, test_user: User):
        """Should generate insight about top spending category"""
        active_subs = []
        new_subs = []
        cancelled_subs = []
        # category_breakdown structure: {category: {'count': int, 'cost': float}}
        category_breakdown = {
            "streaming": {"count": 2, "cost": 50.0},
            "music": {"count": 1, "cost": 10.0},
            "software": {"count": 1, "cost": 100.0},
        }

        insights = SummaryService._generate_insights(
            active_subs, new_subs, cancelled_subs, 160.0, category_breakdown
        )

        assert any(
            "software" in insight.lower() and "top spending" in insight.lower()
            for insight in insights
        )

    def test_generates_cancellation_insight(self, db_session: Session, test_user: User):
        """Should generate insight about cancelled subscriptions"""
        sub1 = Subscription(
            user_id=test_user.id,
            provider="Old Service",
            amount=Decimal("19.99"),
            billing_cycle="monthly",
        )
        active_subs = []
        new_subs = []
        cancelled_subs = [sub1]

        insights = SummaryService._generate_insights(
            active_subs, new_subs, cancelled_subs, 50.0, {}
        )

        assert any("cancelled 1" in insight.lower() for insight in insights)

    def test_generates_multiple_insights(self, db_session: Session, test_user: User):
        """Should generate multiple insights when applicable"""
        sub1 = Subscription(
            user_id=test_user.id,
            provider="Netflix",
            amount=Decimal("15.99"),
            billing_cycle="monthly",
        )
        sub2 = Subscription(
            user_id=test_user.id,
            provider="Gym",
            amount=Decimal("50.00"),
            billing_cycle="monthly",
        )
        sub3 = Subscription(
            user_id=test_user.id,
            provider="Old",
            amount=Decimal("19.99"),
            billing_cycle="monthly",
        )
        active_subs = [sub1]
        new_subs = [sub2]
        cancelled_subs = [sub3]
        category_breakdown = {"streaming": {"count": 1, "cost": 50.0}}

        insights = SummaryService._generate_insights(
            active_subs, new_subs, cancelled_subs, 50.0, category_breakdown
        )

        # Should have multiple insights
        assert len(insights) >= 2


class TestEmptySummary:
    """Tests for _empty_summary method"""

    def test_creates_empty_weekly_summary(self):
        """Should create properly structured empty weekly summary"""
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        result = SummaryService._empty_summary("weekly", start_date, end_date)

        # Dates are formatted strings, not datetime objects
        assert result["period_type"] == "weekly"
        assert result["start_date"] == start_date.strftime("%B %d, %Y")
        assert result["end_date"] == end_date.strftime("%B %d, %Y")
        # Flat structure, not nested
        assert result["total_subscriptions"] == 0
        assert result["total_monthly_cost"] == 0
        assert result["new_subscriptions"] == []
        assert result["cancelled_subscriptions"] == []
        assert result["top_categories"] == []
        assert len(result["insights"]) > 0  # Has default message

    def test_creates_empty_monthly_summary(self):
        """Should create properly structured empty monthly summary"""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        result = SummaryService._empty_summary("monthly", start_date, end_date)

        # Flat structure
        assert result["period_type"] == "monthly"
        assert result["total_subscriptions"] == 0
        assert result["top_subscriptions"] == []


class TestGenerateSummary:
    """Tests for _generate_summary private method"""

    @patch("app.services.summary_service.AIOptimizer.analyze_subscriptions")
    def test_calculates_correct_monthly_costs(
        self,
        mock_ai_analyze: MagicMock,
        db_session: Session,
        test_user: User,
        test_mailbox: Mailbox,
        test_subscriptions,
    ):
        """Should correctly calculate total monthly and yearly costs"""
        mock_ai_analyze.return_value = {
            "recommendations": [],
            "insights": [],
            "potential_savings": 0,
        }

        result = SummaryService.generate_weekly_summary(db_session, test_user)

        # Netflix: 15.99/month
        # Spotify: 9.99/month
        # Gym: 50.00/month
        # Adobe: 599.99/year = ~50/month
        # Total monthly: ~126
        # Total yearly: ~1512

        assert result["total_monthly_cost"] > 120
        assert result["total_monthly_cost"] < 130
        assert result["total_yearly_cost"] > 1400
        assert result["total_yearly_cost"] < 1600

    @patch("app.services.summary_service.AIOptimizer.analyze_subscriptions")
    def test_identifies_top_subscriptions(
        self,
        mock_ai_analyze: MagicMock,
        db_session: Session,
        test_user: User,
        test_mailbox: Mailbox,
        test_subscriptions,
    ):
        """Should identify and rank top subscriptions by monthly cost"""
        mock_ai_analyze.return_value = {
            "recommendations": [],
            "insights": [],
            "potential_savings": 0,
        }

        result = SummaryService.generate_weekly_summary(db_session, test_user)

        top_subs = result["top_subscriptions"]

        # Should have subscriptions
        assert len(top_subs) > 0

        # Should be sorted by monthly cost descending
        # Adobe (~50/month) or Gym (50/month) should be first
        assert top_subs[0]["provider"] in ["Adobe", "Gym Membership"]

    @patch("app.services.summary_service.AIOptimizer.analyze_subscriptions")
    def test_calculates_category_breakdown(
        self,
        mock_ai_analyze: MagicMock,
        db_session: Session,
        test_user: User,
        test_mailbox: Mailbox,
        test_subscriptions,
    ):
        """Should calculate spending breakdown by category"""
        mock_ai_analyze.return_value = {
            "recommendations": [],
            "insights": [],
            "potential_savings": 0,
        }

        result = SummaryService.generate_weekly_summary(db_session, test_user)

        # top_categories is a list of dicts with 'category', 'count', 'cost'
        top_categories = result["top_categories"]
        category_names = [cat["category"] for cat in top_categories]

        # Should have categories
        assert "streaming" in category_names  # Netflix
        assert "music" in category_names  # Spotify
        assert "fitness" in category_names  # Gym
        assert "software" in category_names  # Adobe

        # Should have costs for each category
        streaming_cat = next(
            cat for cat in top_categories if cat["category"] == "streaming"
        )
        assert streaming_cat["cost"] > 0

    @patch("app.services.summary_service.AIOptimizer.analyze_subscriptions")
    def test_calculates_net_change(
        self,
        mock_ai_analyze: MagicMock,
        db_session: Session,
        test_user: User,
        test_mailbox: Mailbox,
        test_subscriptions,
    ):
        """Should calculate net change in subscription count"""
        mock_ai_analyze.return_value = {
            "recommendations": [],
            "insights": [],
            "potential_savings": 0,
        }

        result = SummaryService.generate_weekly_summary(db_session, test_user)

        # Net change = cost_of_new - savings_from_cancellations
        # Gym: 50/month, Old Service: 19.99/month
        # Net change = 50 - 19.99 = 30.01
        assert result["net_change"] > 29
        assert result["net_change"] < 31
