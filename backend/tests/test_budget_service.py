"""Comprehensive tests for budget_service"""
import pytest
from uuid import uuid4
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.services.budget_service import BudgetService
from app.models.budget import Budget
from app.models.subscription import Subscription
from app.models.mailbox import Mailbox
from app.models.user import User


@pytest.fixture
def test_user_with_mailbox(db_session: Session) -> tuple[User, Mailbox]:
    """Create a test user with mailbox"""
    user = User(
        id=uuid4(),
        email="budget@example.com",
        password_hash="hashed",
        salt="salt",
        is_active=True,
        email_verified=True
    )
    db_session.add(user)

    mailbox = Mailbox(
        id=uuid4(),
        user_id=user.id,
        email_address="budget@example.com",
        provider_type="jmap",
        encrypted_credentials="encrypted_test_credentials"
    )
    db_session.add(mailbox)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(mailbox)

    return user, mailbox


@pytest.fixture
def test_subscriptions(db_session: Session, test_user_with_mailbox) -> list[Subscription]:
    """Create test subscriptions with various billing cycles"""
    user, mailbox = test_user_with_mailbox

    subscriptions = [
        Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Netflix",
            amount=Decimal("15.99"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        ),
        Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Spotify",
            amount=Decimal("9.99"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        ),
        Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Adobe CC",
            amount=Decimal("54.99"),
            currency="EUR",
            billing_cycle="monthly",
            category="productivity",
            is_active=True
        ),
        Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Gym",
            amount=Decimal("120.00"),
            currency="EUR",
            billing_cycle="yearly",
            category="fitness",
            is_active=True
        ),
        Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Cancelled Service",
            amount=Decimal("20.00"),
            currency="EUR",
            billing_cycle="monthly",
            category="other",
            is_active=False  # Inactive
        )
    ]

    for sub in subscriptions:
        db_session.add(sub)
    db_session.commit()

    return subscriptions


@pytest.fixture
def test_budget(db_session: Session, test_user_with_mailbox) -> Budget:
    """Create a test budget"""
    user, _ = test_user_with_mailbox

    budget = Budget(
        id=uuid4(),
        user_id=user.id,
        name="Monthly Streaming Budget",
        category="streaming",
        period="monthly",
        limit_amount=Decimal("50.00"),
        currency="EUR",
        alert_threshold=80,
        alert_enabled="true"
    )
    db_session.add(budget)
    db_session.commit()
    db_session.refresh(budget)

    return budget


class TestGetPeriodDates:
    """Tests for _get_period_dates method"""

    def test_calculates_monthly_period(self):
        """Should calculate correct monthly period dates"""
        start, end = BudgetService._get_period_dates('monthly')

        today = datetime.now()
        # Start should be first day of current month
        assert start.day == 1
        assert start.month == today.month
        assert start.year == today.year
        assert start.hour == 0
        assert start.minute == 0

        # End should be last day of current month
        assert end.month == today.month
        assert end.year == today.year

    def test_calculates_quarterly_period(self):
        """Should calculate correct quarterly period dates"""
        start, end = BudgetService._get_period_dates('quarterly')

        # Start should be first day of current quarter
        assert start.day == 1
        assert start.hour == 0

        # Quarter start month should be 1, 4, 7, or 10
        assert start.month in [1, 4, 7, 10]

    def test_calculates_yearly_period(self):
        """Should calculate correct yearly period dates"""
        start, end = BudgetService._get_period_dates('yearly')

        today = datetime.now()
        # Start should be January 1st
        assert start.day == 1
        assert start.month == 1
        assert start.year == today.year

        # End should be December 31st
        assert end.day == 31
        assert end.month == 12
        assert end.year == today.year

    def test_defaults_to_monthly_for_invalid_period(self):
        """Should default to monthly for invalid period"""
        start, end = BudgetService._get_period_dates('invalid')

        # Should behave like monthly
        assert start.day == 1


class TestNormalizeBillingToMonthly:
    """Tests for _normalize_billing_to_monthly method"""

    def test_normalizes_weekly_to_monthly(self):
        """Should convert weekly amount to monthly"""
        result = BudgetService._normalize_billing_to_monthly(10.0, 'weekly')
        assert result == 43.30  # 10 * 4.33

    def test_keeps_monthly_unchanged(self):
        """Should keep monthly amount unchanged"""
        result = BudgetService._normalize_billing_to_monthly(15.99, 'monthly')
        assert result == 15.99

    def test_normalizes_quarterly_to_monthly(self):
        """Should convert quarterly amount to monthly"""
        result = BudgetService._normalize_billing_to_monthly(30.0, 'quarterly')
        assert result == 10.0  # 30 / 3

    def test_normalizes_biannual_to_monthly(self):
        """Should convert biannual amount to monthly"""
        result = BudgetService._normalize_billing_to_monthly(60.0, 'biannual')
        assert result == 10.0  # 60 / 6

    def test_normalizes_yearly_to_monthly(self):
        """Should convert yearly amount to monthly"""
        result = BudgetService._normalize_billing_to_monthly(120.0, 'yearly')
        assert result == 10.0  # 120 / 12

    def test_normalizes_annual_to_monthly(self):
        """Should convert annual amount to monthly"""
        result = BudgetService._normalize_billing_to_monthly(120.0, 'annual')
        assert result == 10.0  # 120 / 12

    def test_handles_zero_amount(self):
        """Should handle zero amount"""
        result = BudgetService._normalize_billing_to_monthly(0.0, 'monthly')
        assert result == 0.0

    def test_handles_none_amount(self):
        """Should handle None amount"""
        result = BudgetService._normalize_billing_to_monthly(None, 'monthly')
        assert result == 0.0

    def test_defaults_to_monthly_for_unknown_cycle(self):
        """Should default to monthly multiplier for unknown cycle"""
        result = BudgetService._normalize_billing_to_monthly(15.0, 'unknown')
        assert result == 15.0


class TestNormalizeToPeriod:
    """Tests for _normalize_to_period method"""

    def test_normalizes_to_monthly(self):
        """Should normalize to monthly period"""
        result = BudgetService._normalize_to_period(120.0, 'yearly', 'monthly')
        assert result == 10.0  # 120 / 12

    def test_normalizes_to_quarterly(self):
        """Should normalize to quarterly period"""
        result = BudgetService._normalize_to_period(10.0, 'monthly', 'quarterly')
        assert result == 30.0  # 10 * 3

    def test_normalizes_to_yearly(self):
        """Should normalize to yearly period"""
        result = BudgetService._normalize_to_period(10.0, 'monthly', 'yearly')
        assert result == 120.0  # 10 * 12

    def test_handles_complex_conversion(self):
        """Should handle conversion from weekly to quarterly"""
        result = BudgetService._normalize_to_period(10.0, 'weekly', 'quarterly')
        # 10 * 4.33 = 43.30 (monthly), then 43.30 * 3 = 129.90 (quarterly)
        assert result == pytest.approx(129.90, rel=0.01)


class TestCalculateSpending:
    """Tests for calculate_spending method"""

    def test_calculates_total_spending(
        self,
        db_session: Session,
        test_user_with_mailbox,
        test_subscriptions
    ):
        """Should calculate total spending for all active subscriptions"""
        user, _ = test_user_with_mailbox

        spending = BudgetService.calculate_spending(
            db_session,
            str(user.id),
            period='monthly'
        )

        # Netflix 15.99 + Spotify 9.99 + Adobe 54.99 + Gym (120/12=10) = 90.97
        assert spending == pytest.approx(90.97, rel=0.01)

    def test_filters_by_category(
        self,
        db_session: Session,
        test_user_with_mailbox,
        test_subscriptions
    ):
        """Should filter spending by category"""
        user, _ = test_user_with_mailbox

        spending = BudgetService.calculate_spending(
            db_session,
            str(user.id),
            category='streaming',
            period='monthly'
        )

        # Netflix 15.99 + Spotify 9.99 = 25.98
        assert spending == pytest.approx(25.98, rel=0.01)

    def test_normalizes_to_quarterly(
        self,
        db_session: Session,
        test_user_with_mailbox,
        test_subscriptions
    ):
        """Should normalize spending to quarterly period"""
        user, _ = test_user_with_mailbox

        spending = BudgetService.calculate_spending(
            db_session,
            str(user.id),
            period='quarterly'
        )

        # Monthly total * 3
        # (15.99 + 9.99 + 54.99 + 10) * 3 = 90.97 * 3 = 272.91
        assert spending == pytest.approx(272.91, rel=0.01)

    def test_normalizes_to_yearly(
        self,
        db_session: Session,
        test_user_with_mailbox,
        test_subscriptions
    ):
        """Should normalize spending to yearly period"""
        user, _ = test_user_with_mailbox

        spending = BudgetService.calculate_spending(
            db_session,
            str(user.id),
            period='yearly'
        )

        # Monthly total * 12
        # 90.97 * 12 = 1091.64
        assert spending == pytest.approx(1091.64, rel=0.01)

    def test_returns_zero_for_user_with_no_mailboxes(self, db_session: Session):
        """Should return 0 for user with no mailboxes"""
        fake_user_id = str(uuid4())

        spending = BudgetService.calculate_spending(
            db_session,
            fake_user_id,
            period='monthly'
        )

        assert spending == 0.0

    def test_ignores_inactive_subscriptions(
        self,
        db_session: Session,
        test_user_with_mailbox,
        test_subscriptions
    ):
        """Should ignore inactive subscriptions"""
        user, _ = test_user_with_mailbox

        # Cancelled Service (20.00) should not be included
        spending = BudgetService.calculate_spending(
            db_session,
            str(user.id),
            period='monthly'
        )

        # Should not include the 20.00 from Cancelled Service
        assert spending == pytest.approx(90.97, rel=0.01)

    def test_handles_subscriptions_without_amounts(
        self,
        db_session: Session,
        test_user_with_mailbox
    ):
        """Should handle subscriptions without amounts"""
        user, mailbox = test_user_with_mailbox

        sub_no_amount = Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Free Service",
            amount=None,  # No amount
            currency="EUR",
            billing_cycle="monthly",
            category="other",
            is_active=True
        )
        db_session.add(sub_no_amount)
        db_session.commit()

        spending = BudgetService.calculate_spending(
            db_session,
            str(user.id),
            period='monthly'
        )

        # Should not error, just ignore None amounts
        assert spending >= 0.0


class TestGetBudgetStatus:
    """Tests for get_budget_status method"""

    def test_returns_good_status_within_budget(
        self,
        db_session: Session,
        test_budget,
        test_subscriptions
    ):
        """Should return 'good' status when within budget"""
        status = BudgetService.get_budget_status(db_session, test_budget)

        # Streaming: 15.99 + 9.99 = 25.98, Limit: 50.00
        assert status['status'] == 'good'
        assert status['current_spending'] == pytest.approx(25.98, rel=0.01)
        assert status['limit_amount'] == 50.0
        assert status['remaining'] == pytest.approx(24.02, rel=0.01)
        assert status['percentage_used'] < 80  # Below alert threshold

    def test_returns_warning_status_at_threshold(
        self,
        db_session: Session,
        test_user_with_mailbox
    ):
        """Should return 'warning' status at alert threshold"""
        user, mailbox = test_user_with_mailbox

        # Create budget with low limit to trigger warning
        budget = Budget(
            id=uuid4(),
            user_id=user.id,
            name="Tight Budget",
            category="streaming",
            period="monthly",
            limit_amount=Decimal("30.00"),  # Close to 25.98 spending
            currency="EUR",
            alert_threshold=80,
            alert_enabled="true"
        )
        db_session.add(budget)

        # Add subscriptions to trigger warning
        sub1 = Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Service1",
            amount=Decimal("25.00"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        )
        db_session.add(sub1)
        db_session.commit()
        db_session.refresh(budget)

        status = BudgetService.get_budget_status(db_session, budget)

        # 25.00 / 30.00 = 83.33% > 80%
        assert status['status'] == 'warning'
        assert status['percentage_used'] >= 80
        assert status['percentage_used'] < 100

    def test_returns_exceeded_status_over_budget(
        self,
        db_session: Session,
        test_user_with_mailbox
    ):
        """Should return 'exceeded' status when over budget"""
        user, mailbox = test_user_with_mailbox

        # Create budget with very low limit
        budget = Budget(
            id=uuid4(),
            user_id=user.id,
            name="Very Tight Budget",
            category="streaming",
            period="monthly",
            limit_amount=Decimal("20.00"),
            currency="EUR",
            alert_threshold=80,
            alert_enabled="true"
        )
        db_session.add(budget)

        # Add subscriptions that exceed budget
        sub1 = Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Service1",
            amount=Decimal("25.00"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        )
        db_session.add(sub1)
        db_session.commit()
        db_session.refresh(budget)

        status = BudgetService.get_budget_status(db_session, budget)

        # 25.00 / 20.00 = 125% >= 100%
        assert status['status'] == 'exceeded'
        assert status['percentage_used'] >= 100
        assert status['remaining'] < 0

    def test_includes_period_dates(
        self,
        db_session: Session,
        test_budget,
        test_subscriptions
    ):
        """Should include period start and end dates"""
        status = BudgetService.get_budget_status(db_session, test_budget)

        assert 'period_start' in status
        assert 'period_end' in status
        assert isinstance(status['period_start'], str)
        assert isinstance(status['period_end'], str)

    def test_includes_all_budget_fields(
        self,
        db_session: Session,
        test_budget,
        test_subscriptions
    ):
        """Should include all budget information"""
        status = BudgetService.get_budget_status(db_session, test_budget)

        assert status['budget_id'] == str(test_budget.id)
        assert status['name'] == 'Monthly Streaming Budget'
        assert status['category'] == 'streaming'
        assert status['period'] == 'monthly'
        assert status['alert_threshold'] == 80
        assert status['alert_enabled'] is True
        assert status['currency'] == 'EUR'


class TestGetAllBudgetsStatus:
    """Tests for get_all_budgets_status method"""

    def test_returns_all_user_budgets(
        self,
        db_session: Session,
        test_user_with_mailbox,
        test_subscriptions
    ):
        """Should return status for all user budgets"""
        user, _ = test_user_with_mailbox

        # Create multiple budgets
        budgets = [
            Budget(
                id=uuid4(),
                user_id=user.id,
                name="Streaming Budget",
                category="streaming",
                period="monthly",
                limit_amount=Decimal("50.00"),
                currency="EUR",
                alert_threshold=80,
                alert_enabled="true"
            ),
            Budget(
                id=uuid4(),
                user_id=user.id,
                name="Overall Budget",
                category=None,  # Overall
                period="monthly",
                limit_amount=Decimal("200.00"),
                currency="EUR",
                alert_threshold=90,
                alert_enabled="true"
            )
        ]

        for budget in budgets:
            db_session.add(budget)
        db_session.commit()

        statuses = BudgetService.get_all_budgets_status(db_session, str(user.id))

        assert len(statuses) == 2
        assert all('budget_id' in s for s in statuses)
        assert all('status' in s for s in statuses)

    def test_returns_empty_list_for_no_budgets(self, db_session: Session):
        """Should return empty list for user with no budgets"""
        fake_user_id = str(uuid4())

        statuses = BudgetService.get_all_budgets_status(db_session, fake_user_id)

        assert statuses == []


class TestCheckBudgetAlerts:
    """Tests for check_budget_alerts method"""

    def test_returns_alerts_for_warning_budgets(
        self,
        db_session: Session,
        test_user_with_mailbox
    ):
        """Should return alerts for budgets at warning threshold"""
        user, mailbox = test_user_with_mailbox

        # Create budget at warning level
        budget = Budget(
            id=uuid4(),
            user_id=user.id,
            name="Warning Budget",
            category="streaming",
            period="monthly",
            limit_amount=Decimal("30.00"),
            currency="EUR",
            alert_threshold=80,
            alert_enabled="true"
        )
        db_session.add(budget)

        sub = Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Service",
            amount=Decimal("25.00"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        )
        db_session.add(sub)
        db_session.commit()

        alerts = BudgetService.check_budget_alerts(db_session, str(user.id))

        assert len(alerts) == 1
        assert alerts[0]['alert_type'] == 'warning'
        assert 'Warning Budget' in alerts[0]['message']

    def test_returns_alerts_for_exceeded_budgets(
        self,
        db_session: Session,
        test_user_with_mailbox
    ):
        """Should return alerts for exceeded budgets"""
        user, mailbox = test_user_with_mailbox

        # Create budget that will be exceeded
        budget = Budget(
            id=uuid4(),
            user_id=user.id,
            name="Exceeded Budget",
            category="streaming",
            period="monthly",
            limit_amount=Decimal("20.00"),
            currency="EUR",
            alert_threshold=80,
            alert_enabled="true"
        )
        db_session.add(budget)

        sub = Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Service",
            amount=Decimal("25.00"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        )
        db_session.add(sub)
        db_session.commit()

        alerts = BudgetService.check_budget_alerts(db_session, str(user.id))

        assert len(alerts) == 1
        assert alerts[0]['alert_type'] == 'exceeded'
        assert 'Exceeded Budget' in alerts[0]['message']

    def test_ignores_budgets_with_alerts_disabled(
        self,
        db_session: Session,
        test_user_with_mailbox
    ):
        """Should ignore budgets with alerts disabled"""
        user, mailbox = test_user_with_mailbox

        budget = Budget(
            id=uuid4(),
            user_id=user.id,
            name="Disabled Alerts",
            category="streaming",
            period="monthly",
            limit_amount=Decimal("20.00"),
            currency="EUR",
            alert_threshold=80,
            alert_enabled="false"  # Disabled
        )
        db_session.add(budget)

        sub = Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Service",
            amount=Decimal("25.00"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        )
        db_session.add(sub)
        db_session.commit()

        alerts = BudgetService.check_budget_alerts(db_session, str(user.id))

        # Should not include this budget
        assert len(alerts) == 0

    def test_returns_empty_list_for_good_budgets(
        self,
        db_session: Session,
        test_budget,
        test_subscriptions
    ):
        """Should return empty list when all budgets are good"""
        user, _ = test_subscriptions[0].user, test_subscriptions[0].mailbox

        alerts = BudgetService.check_budget_alerts(db_session, str(user.id))

        # Streaming budget is within limits
        assert len(alerts) == 0

    def test_includes_budget_details_in_alert(
        self,
        db_session: Session,
        test_user_with_mailbox
    ):
        """Should include budget details in alert message"""
        user, mailbox = test_user_with_mailbox

        budget = Budget(
            id=uuid4(),
            user_id=user.id,
            name="Test Budget",
            category="streaming",
            period="monthly",
            limit_amount=Decimal("30.00"),
            currency="EUR",
            alert_threshold=80,
            alert_enabled="true"
        )
        db_session.add(budget)

        sub = Subscription(
            id=uuid4(),
            user_id=user.id,
            mailbox_id=mailbox.id,
            provider="Service",
            amount=Decimal("25.00"),
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True
        )
        db_session.add(sub)
        db_session.commit()

        alerts = BudgetService.check_budget_alerts(db_session, str(user.id))

        assert len(alerts) == 1
        alert = alerts[0]
        assert 'budget' in alert
        assert 'alert_type' in alert
        assert 'message' in alert
        assert '25.0' in alert['message']  # Current spending
        assert '30.0' in alert['message']  # Limit
        assert 'EUR' in alert['message']  # Currency
