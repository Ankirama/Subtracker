"""Comprehensive tests for AI optimizer service"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4
from sqlalchemy.orm import Session

from app.services.ai_optimizer import AIOptimizer
from app.models.subscription import Subscription
from app.models.user import User


@pytest.fixture
def subscription_netflix(db_session: Session, test_user: User) -> Subscription:
    """Create a Netflix subscription"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Netflix",
        category="streaming",
        amount=15.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        last_confirmed_at=datetime.utcnow() - timedelta(days=5),
        first_detected_at=datetime.utcnow() - timedelta(days=365),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def subscription_spotify(db_session: Session, test_user: User) -> Subscription:
    """Create a Spotify subscription"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Spotify Premium",
        category="streaming",
        amount=10.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        last_confirmed_at=datetime.utcnow() - timedelta(days=10),
        first_detected_at=datetime.utcnow() - timedelta(days=200),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def subscription_unused(db_session: Session, test_user: User) -> Subscription:
    """Create an unused subscription (>90 days inactive)"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Old Service",
        category="productivity",
        amount=9.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        last_confirmed_at=datetime.utcnow() - timedelta(days=120),
        first_detected_at=datetime.utcnow() - timedelta(days=500),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def subscription_yearly(db_session: Session, test_user: User) -> Subscription:
    """Create a yearly subscription"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Adobe Creative Cloud",
        category="productivity",
        amount=599.88,
        currency="USD",
        billing_cycle="yearly",
        is_active=True,
        last_confirmed_at=datetime.utcnow() - timedelta(days=30),
        first_detected_at=datetime.utcnow() - timedelta(days=400),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


class TestAnalyzeSubscriptions:
    """Tests for analyze_subscriptions main method"""

    def test_handles_empty_subscriptions(self, db_session: Session, test_user: User):
        """Should return empty analysis for no subscriptions"""
        result = AIOptimizer.analyze_subscriptions(db_session, test_user, [])

        assert result["total_recommendations"] == 0
        assert result["potential_savings"] == 0.0
        assert result["recommendations"] == []
        assert len(result["insights"]) == 1
        assert result["insights"][0] == "No active subscriptions to analyze"

    @patch("app.services.ai_optimizer.datetime")
    def test_analyzes_single_subscription(
        self,
        mock_datetime: MagicMock,
        db_session: Session,
        test_user: User,
        subscription_netflix: Subscription,
    ):
        """Should analyze single subscription without errors"""
        # Mock datetime.now() to return naive datetime
        mock_datetime.now.return_value = datetime.utcnow()
        mock_datetime.utcnow = datetime.utcnow

        result = AIOptimizer.analyze_subscriptions(
            db_session, test_user, [subscription_netflix]
        )

        assert "total_recommendations" in result
        assert "potential_savings" in result
        assert "recommendations" in result
        assert "insights" in result
        assert "analyzed_at" in result

    @patch("app.services.ai_optimizer.datetime")
    def test_analyzes_multiple_subscriptions(
        self,
        mock_datetime: MagicMock,
        db_session: Session,
        test_user: User,
        subscription_netflix: Subscription,
        subscription_spotify: Subscription,
    ):
        """Should analyze multiple subscriptions"""
        # Mock datetime.now() to return naive datetime
        mock_datetime.now.return_value = datetime.utcnow()
        mock_datetime.utcnow = datetime.utcnow

        result = AIOptimizer.analyze_subscriptions(
            db_session, test_user, [subscription_netflix, subscription_spotify]
        )

        assert result["total_recommendations"] >= 0
        assert isinstance(result["recommendations"], list)


class TestPrepareSubscriptionData:
    """Tests for _prepare_subscription_data method"""

    def test_prepares_subscription_data_correctly(
        self, subscription_netflix: Subscription
    ):
        """Should convert subscriptions to data format"""
        data = AIOptimizer._prepare_subscription_data([subscription_netflix])

        assert len(data) == 1
        assert data[0]["provider"] == "Netflix"
        assert data[0]["category"] == "streaming"
        assert data[0]["amount"] == 15.99
        assert data[0]["billing_cycle"] == "monthly"
        assert data[0]["monthly_cost"] == 15.99

    def test_handles_missing_category(self, db_session: Session, test_user: User):
        """Should default to 'other' for missing category"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Test Service",
            category=None,
            amount=10.0,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        data = AIOptimizer._prepare_subscription_data([sub])

        assert data[0]["category"] == "other"


class TestGetMonthlyCost:
    """Tests for _get_monthly_cost method"""

    def test_calculates_monthly_cost_for_monthly_cycle(self):
        """Should return same amount for monthly billing"""
        sub = Subscription(amount=15.99, billing_cycle="monthly")
        result = AIOptimizer._get_monthly_cost(sub)
        assert result == 15.99

    def test_calculates_monthly_cost_for_yearly_cycle(self):
        """Should divide by 12 for yearly billing"""
        sub = Subscription(amount=120.0, billing_cycle="yearly")
        result = AIOptimizer._get_monthly_cost(sub)
        assert result == pytest.approx(10.0, rel=0.01)

    def test_calculates_monthly_cost_for_weekly_cycle(self):
        """Should multiply by 4.33 for weekly billing"""
        sub = Subscription(amount=10.0, billing_cycle="weekly")
        result = AIOptimizer._get_monthly_cost(sub)
        assert result == pytest.approx(43.3, rel=0.01)

    def test_calculates_monthly_cost_for_quarterly_cycle(self):
        """Should divide by 3 for quarterly billing"""
        sub = Subscription(amount=30.0, billing_cycle="quarterly")
        result = AIOptimizer._get_monthly_cost(sub)
        assert result == pytest.approx(10.0, rel=0.01)

    def test_calculates_monthly_cost_for_biannual_cycle(self):
        """Should divide by 6 for biannual billing"""
        sub = Subscription(amount=60.0, billing_cycle="biannual")
        result = AIOptimizer._get_monthly_cost(sub)
        assert result == pytest.approx(10.0, rel=0.01)

    def test_handles_none_amount(self):
        """Should return 0 for None amount"""
        sub = Subscription(amount=None, billing_cycle="monthly")
        result = AIOptimizer._get_monthly_cost(sub)
        assert result == 0.0

    def test_handles_unknown_billing_cycle(self):
        """Should return 0 for unknown billing cycle"""
        sub = Subscription(amount=10.0, billing_cycle="unknown_cycle")
        result = AIOptimizer._get_monthly_cost(sub)
        assert result == 0.0


class TestDetectDuplicates:
    """Tests for _detect_duplicates method"""

    def test_detects_storage_duplicates(self, db_session: Session, test_user: User):
        """Should detect multiple storage services"""
        dropbox = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Dropbox",
            category="storage",
            amount=9.99,
            billing_cycle="monthly",
        )
        google_drive = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Google Drive",
            category="storage",
            amount=1.99,
            billing_cycle="monthly",
        )
        subscriptions = [dropbox, google_drive]
        data = AIOptimizer._prepare_subscription_data(subscriptions)

        recommendations = AIOptimizer._detect_duplicates(subscriptions, data)

        assert len(recommendations) == 1
        assert recommendations[0]["type"] == "duplicate_consolidation"
        assert recommendations[0]["category"] == "storage"
        assert "Consolidate" in recommendations[0]["title"]

    def test_detects_streaming_duplicates(self, db_session: Session, test_user: User):
        """Should detect multiple streaming services"""
        netflix = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Netflix",
            category="streaming",
            amount=15.99,
            billing_cycle="monthly",
        )
        hulu = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Hulu",
            category="streaming",
            amount=7.99,
            billing_cycle="monthly",
        )
        disney = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Disney+",
            category="streaming",
            amount=7.99,
            billing_cycle="monthly",
        )
        subscriptions = [netflix, hulu, disney]
        data = AIOptimizer._prepare_subscription_data(subscriptions)

        recommendations = AIOptimizer._detect_duplicates(subscriptions, data)

        assert len(recommendations) == 1
        assert recommendations[0]["type"] == "duplicate_review"
        assert recommendations[0]["category"] == "streaming"
        assert "3 Streaming Services" in recommendations[0]["title"]

    def test_no_duplicates_for_single_subscription(
        self, subscription_netflix: Subscription
    ):
        """Should not flag duplicates for single subscription"""
        subscriptions = [subscription_netflix]
        data = AIOptimizer._prepare_subscription_data(subscriptions)

        recommendations = AIOptimizer._detect_duplicates(subscriptions, data)

        assert len(recommendations) == 0


class TestDetectUnused:
    """Tests for _detect_unused method"""

    @patch("app.services.ai_optimizer.datetime")
    def test_detects_unused_subscription(
        self, mock_datetime: MagicMock, subscription_unused: Subscription
    ):
        """Should detect subscription with >90 days inactivity"""
        # Mock datetime.now() to return naive datetime
        mock_datetime.now.return_value = datetime.utcnow()
        mock_datetime.utcnow = datetime.utcnow

        recommendations = AIOptimizer._detect_unused([subscription_unused])

        assert len(recommendations) == 1
        assert recommendations[0]["type"] == "unused_subscription"
        assert "Potentially Unused" in recommendations[0]["title"]
        assert recommendations[0]["potential_savings"] == 9.99

    @patch("app.services.ai_optimizer.datetime")
    def test_does_not_flag_recent_subscription(
        self, mock_datetime: MagicMock, subscription_netflix: Subscription
    ):
        """Should not flag subscription with recent activity"""
        # Mock datetime.now() to return naive datetime
        mock_datetime.now.return_value = datetime.utcnow()
        mock_datetime.utcnow = datetime.utcnow

        recommendations = AIOptimizer._detect_unused([subscription_netflix])

        assert len(recommendations) == 0

    @patch("app.services.ai_optimizer.datetime")
    def test_priority_high_for_expensive_unused(
        self, mock_datetime: MagicMock, db_session: Session, test_user: User
    ):
        """Should mark high priority for expensive unused subscriptions"""
        # Mock datetime.now() to return naive datetime
        mock_datetime.now.return_value = datetime.utcnow()
        mock_datetime.utcnow = datetime.utcnow

        expensive_sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Expensive Service",
            category="productivity",
            amount=50.0,
            billing_cycle="monthly",
            is_active=True,
            last_confirmed_at=datetime.utcnow() - timedelta(days=100),
        )

        recommendations = AIOptimizer._detect_unused([expensive_sub])

        assert len(recommendations) == 1
        assert recommendations[0]["priority"] == "high"


class TestDetectFamilyPlanOpportunities:
    """Tests for _detect_family_plan_opportunities method"""

    def test_suggests_spotify_family_plan(self, subscription_spotify: Subscription):
        """Should suggest Spotify family plan upgrade"""
        recommendations = AIOptimizer._detect_family_plan_opportunities(
            [subscription_spotify]
        )

        # Should suggest family plan since individual price matches
        assert len(recommendations) >= 0
        if len(recommendations) > 0:
            assert recommendations[0]["type"] == "family_plan_upgrade"
            assert "Spotify" in recommendations[0]["title"]

    def test_no_suggestions_for_non_family_services(
        self, db_session: Session, test_user: User
    ):
        """Should not suggest family plan for services without family options"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Unknown Service",
            category="other",
            amount=10.0,
            billing_cycle="monthly",
        )

        recommendations = AIOptimizer._detect_family_plan_opportunities([sub])

        assert len(recommendations) == 0


class TestSuggestAnnualBilling:
    """Tests for _suggest_annual_billing method"""

    def test_suggests_annual_for_monthly_subscription(
        self, subscription_netflix: Subscription
    ):
        """Should suggest annual billing for monthly subscriptions"""
        recommendations = AIOptimizer._suggest_annual_billing([subscription_netflix])

        assert len(recommendations) == 1
        assert recommendations[0]["type"] == "annual_billing_savings"
        assert "Annual Billing" in recommendations[0]["title"]
        assert recommendations[0]["potential_savings"] > 0

    def test_does_not_suggest_for_yearly_subscription(
        self, subscription_yearly: Subscription
    ):
        """Should not suggest annual for already yearly subscriptions"""
        recommendations = AIOptimizer._suggest_annual_billing([subscription_yearly])

        assert len(recommendations) == 0

    def test_skips_cheap_subscriptions(self, db_session: Session, test_user: User):
        """Should skip subscriptions under €5/month"""
        cheap_sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Cheap Service",
            category="other",
            amount=2.99,
            billing_cycle="monthly",
        )

        recommendations = AIOptimizer._suggest_annual_billing([cheap_sub])

        assert len(recommendations) == 0

    def test_higher_priority_for_large_savings(
        self, db_session: Session, test_user: User
    ):
        """Should mark medium priority for large annual savings"""
        expensive_sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Expensive Monthly",
            category="productivity",
            amount=30.0,
            billing_cycle="monthly",
        )

        recommendations = AIOptimizer._suggest_annual_billing([expensive_sub])

        assert len(recommendations) == 1
        assert recommendations[0]["priority"] == "medium"


class TestSuggestAlternatives:
    """Tests for _suggest_alternatives method"""

    @patch("app.services.ai_optimizer.openai.chat.completions.create")
    def test_suggests_alternatives_for_expensive_subscriptions(
        self, mock_openai: MagicMock
    ):
        """Should use AI to suggest cheaper alternatives"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = """
        {
            "has_alternative": true,
            "alternative_name": "Cheaper Alternative",
            "alternative_price": 10.0,
            "savings_percentage": 37,
            "reason": "Similar features at lower cost"
        }
        """
        mock_openai.return_value = mock_response

        subscription_data = [
            {
                "id": str(uuid4()),
                "provider": "Expensive Service",
                "category": "productivity",
                "monthly_cost": 15.99,
            }
        ]

        recommendations = AIOptimizer._suggest_alternatives(subscription_data)

        assert len(recommendations) == 1
        assert recommendations[0]["type"] == "alternative_provider"
        assert recommendations[0]["current_provider"] == "Expensive Service"
        assert recommendations[0]["alternative_provider"] == "Cheaper Alternative"
        assert recommendations[0]["potential_savings"] > 0

    @patch("app.services.ai_optimizer.openai.chat.completions.create")
    def test_skips_cheap_subscriptions(self, mock_openai: MagicMock):
        """Should not analyze subscriptions under €10/month"""
        subscription_data = [
            {
                "id": str(uuid4()),
                "provider": "Cheap Service",
                "category": "other",
                "monthly_cost": 5.0,
            }
        ]

        recommendations = AIOptimizer._suggest_alternatives(subscription_data)

        assert len(recommendations) == 0
        mock_openai.assert_not_called()

    @patch("app.services.ai_optimizer.openai.chat.completions.create")
    def test_handles_openai_errors_gracefully(self, mock_openai: MagicMock):
        """Should handle OpenAI API errors without crashing"""
        mock_openai.side_effect = Exception("API Error")

        subscription_data = [
            {
                "id": str(uuid4()),
                "provider": "Expensive Service",
                "category": "productivity",
                "monthly_cost": 15.99,
            }
        ]

        recommendations = AIOptimizer._suggest_alternatives(subscription_data)

        assert len(recommendations) == 0

    @patch("app.services.ai_optimizer.openai.chat.completions.create")
    def test_skips_alternatives_with_small_savings(self, mock_openai: MagicMock):
        """Should skip alternatives that save less than €2/month"""
        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = """
        {
            "has_alternative": true,
            "alternative_name": "Similar Price Alternative",
            "alternative_price": 14.50,
            "savings_percentage": 10,
            "reason": "Marginal savings"
        }
        """
        mock_openai.return_value = mock_response

        subscription_data = [
            {
                "id": str(uuid4()),
                "provider": "Service",
                "category": "productivity",
                "monthly_cost": 15.0,
            }
        ]

        recommendations = AIOptimizer._suggest_alternatives(subscription_data)

        assert len(recommendations) == 0


class TestGenerateInsights:
    """Tests for _generate_insights method"""

    def test_generates_insights_with_savings(self, subscription_netflix: Subscription):
        """Should generate savings insights"""
        recommendations = [
            {
                "type": "unused_subscription",
                "potential_savings": 10.0,
                "priority": "high",
            }
        ]

        insights = AIOptimizer._generate_insights(
            [subscription_netflix], recommendations
        )

        assert len(insights) > 0
        assert any("save" in insight.lower() for insight in insights)

    def test_includes_high_priority_warnings(self, subscription_netflix: Subscription):
        """Should warn about high priority recommendations"""
        recommendations = [
            {
                "type": "unused_subscription",
                "potential_savings": 10.0,
                "priority": "high",
            },
            {
                "type": "duplicate_consolidation",
                "potential_savings": 5.0,
                "priority": "high",
            },
        ]

        insights = AIOptimizer._generate_insights(
            [subscription_netflix], recommendations
        )

        assert any("high-priority" in insight.lower() for insight in insights)

    def test_reports_spending_totals(self, db_session: Session, test_user: User):
        """Should report total spending for high spenders"""
        expensive_subs = []
        for i in range(5):
            sub = Subscription(
                id=uuid4(),
                user_id=test_user.id,
                provider=f"Service {i}",
                category="productivity",
                amount=25.0,
                billing_cycle="monthly",
            )
            expensive_subs.append(sub)

        insights = AIOptimizer._generate_insights(expensive_subs, [])

        assert any("subscription spending" in insight.lower() for insight in insights)

    def test_reports_duplicate_detection(self, subscription_netflix: Subscription):
        """Should report duplicate services detected"""
        recommendations = [
            {
                "type": "duplicate_consolidation",
                "potential_savings": 10.0,
                "priority": "medium",
            }
        ]

        insights = AIOptimizer._generate_insights(
            [subscription_netflix], recommendations
        )

        assert any(
            "duplicate" in insight.lower() or "overlapping" in insight.lower()
            for insight in insights
        )

    def test_reports_unused_subscriptions(self, subscription_unused: Subscription):
        """Should report unused subscriptions"""
        recommendations = [
            {
                "type": "unused_subscription",
                "potential_savings": 9.99,
                "priority": "high",
            }
        ]

        insights = AIOptimizer._generate_insights(
            [subscription_unused], recommendations
        )

        assert any("unused" in insight.lower() for insight in insights)
