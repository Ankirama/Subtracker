"""
Tests for the RenewalCalculator service.

Tests cover:
- Renewal date calculation from email patterns
- Billing cycle calculation
- Inactivity detection
- Trial detection logic
- Reactivation scenarios
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

from app.services.renewal_calculator import RenewalCalculator


class TestRenewalCalculatorTrialDetection:
    """Test trial detection and confirmation logic."""

    def test_single_email_with_trial_detected(self, db_session):
        """Single email + trial detected = trial status, unconfirmed, inactive."""
        calculator = RenewalCalculator(db_session)

        email_dates = [datetime.now(timezone.utc)]
        email_contents = ["Your free trial starts today!"]
        trial_metadata = {"trial_detected": True, "trial_keywords": ["free trial"]}

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=trial_metadata,
            )
        )

        assert trial_status == "trial"
        assert is_confirmed is False
        assert is_active is False  # Single email = inactive

    def test_two_emails_with_trial_detected(self, db_session):
        """Two emails + trial detected = converted status, confirmed, active."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        email_dates = [now, now - timedelta(days=15)]
        email_contents = [
            "Your subscription has been renewed",
            "Your free trial starts today!",
        ]
        trial_metadata = {"trial_detected": True, "trial_keywords": ["free trial"]}

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=trial_metadata,
            )
        )

        assert trial_status == "converted"
        assert is_confirmed is True
        assert is_active is True

    def test_single_email_no_trial_detected(self, db_session):
        """Single email + no trial = confirmed and active (recent email)."""
        calculator = RenewalCalculator(db_session)

        email_dates = [datetime.now(timezone.utc)]
        email_contents = ["Your subscription has been created"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert trial_status == "none"
        assert is_confirmed is True  # No trial detected, so confirmed
        assert is_active is True  # Active because email is recent

    def test_two_emails_no_trial(self, db_session):
        """Two emails + no trial = confirmed and active."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        email_dates = [now, now - timedelta(days=30)]
        email_contents = [
            "Your subscription has been renewed",
            "Your subscription has been created",
        ]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert trial_status == "none"
        assert is_confirmed is True
        assert is_active is True


class TestRenewalCalculatorPatternExtraction:
    """Test renewal date extraction from email patterns."""

    def test_apple_renewal_pattern_standard(self, db_session):
        """Test Apple 'Renews 25 November 2025' pattern."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        email_dates = [now, now - timedelta(days=30)]
        email_contents = ["Your subscription Renews 25 December 2025", "Previous email"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="Apple",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert renewal_date is not None
        assert renewal_date.day == 25
        assert renewal_date.month == 12
        assert renewal_date.year == 2025

    def test_generic_next_payment_pattern(self, db_session):
        """Test generic 'next payment' pattern."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        email_dates = [now, now - timedelta(days=30)]
        email_contents = [
            "Your next payment will be processed on January 15, 2026",
            "Previous email",
        ]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="GenericProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert renewal_date is not None
        assert renewal_date.day == 15
        assert renewal_date.month == 1
        assert renewal_date.year == 2026

    def test_iso_format_billing_date(self, db_session):
        """Test ISO format billing date pattern."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        email_dates = [now, now - timedelta(days=30)]
        email_contents = ["Billing date: 2025-12-20", "Previous email"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="GenericProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert renewal_date is not None
        assert renewal_date.day == 20
        assert renewal_date.month == 12
        assert renewal_date.year == 2025


class TestRenewalCalculatorBillingCycle:
    """Test billing cycle-based renewal calculation."""

    def test_monthly_billing_cycle(self, db_session):
        """Calculate renewal date for monthly billing cycle."""
        calculator = RenewalCalculator(db_session)

        # Last email was exactly 30 days ago
        last_email_date = datetime.now(timezone.utc) - timedelta(days=30)
        email_dates = [last_email_date, last_email_date - timedelta(days=30)]
        email_contents = ["Subscription renewed", "Subscription renewed"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert renewal_date is not None
        # Should be approximately 1 month from last email
        expected = last_email_date + relativedelta(months=1)
        assert abs((renewal_date - expected).days) <= 1  # Allow 1 day difference

    def test_yearly_billing_cycle(self, db_session):
        """Calculate renewal date for yearly billing cycle."""
        calculator = RenewalCalculator(db_session)

        last_email_date = datetime.now(timezone.utc) - timedelta(days=100)
        email_dates = [last_email_date, last_email_date - timedelta(days=365)]
        email_contents = ["Yearly renewal", "Yearly renewal"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="yearly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert renewal_date is not None
        expected = last_email_date + relativedelta(years=1)
        assert abs((renewal_date - expected).days) <= 1

    def test_quarterly_billing_cycle(self, db_session):
        """Calculate renewal date for quarterly billing cycle."""
        calculator = RenewalCalculator(db_session)

        last_email_date = datetime.now(timezone.utc) - timedelta(days=45)
        email_dates = [last_email_date, last_email_date - timedelta(days=90)]
        email_contents = ["Quarterly renewal", "Quarterly renewal"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="quarterly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert renewal_date is not None
        expected = last_email_date + relativedelta(months=3)
        assert abs((renewal_date - expected).days) <= 1


class TestRenewalCalculatorInactivityDetection:
    """Test inactivity detection based on email frequency."""

    def test_inactive_monthly_subscription_two_cycles(self, db_session):
        """Monthly subscription with no email for >2 cycles should be inactive."""
        calculator = RenewalCalculator(db_session)

        # Last email was 65 days ago (> 2 monthly cycles)
        last_email_date = datetime.now(timezone.utc) - timedelta(days=65)
        email_dates = [last_email_date, last_email_date - timedelta(days=30)]
        email_contents = ["Renewal", "Renewal"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert is_active is False  # > 2 cycles = inactive

    def test_active_monthly_subscription_within_cycles(self, db_session):
        """Monthly subscription with recent email should be active."""
        calculator = RenewalCalculator(db_session)

        # Last email was 25 days ago (< 2 monthly cycles)
        last_email_date = datetime.now(timezone.utc) - timedelta(days=25)
        email_dates = [last_email_date, last_email_date - timedelta(days=30)]
        email_contents = ["Renewal", "Renewal"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert is_active is True

    def test_inactive_yearly_subscription(self, db_session):
        """Yearly subscription with no email for >2 years should be inactive."""
        calculator = RenewalCalculator(db_session)

        # Last email was 750 days ago (> 2 years)
        last_email_date = datetime.now(timezone.utc) - timedelta(days=750)
        email_dates = [last_email_date, last_email_date - timedelta(days=365)]
        email_contents = ["Annual renewal", "Annual renewal"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="yearly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert is_active is False


class TestRenewalCalculatorReactivation:
    """Test reactivation detection logic."""

    def test_reactivation_after_long_gap(self, db_session):
        """Subscription with large gap then new email should detect reactivation."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        # New email today, but previous was 6 months ago
        email_dates = [now, now - timedelta(days=180)]
        email_contents = ["Welcome back!", "Previous renewal"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        # Should be active again due to recent email
        assert is_active is True
        assert is_confirmed is True


class TestRenewalCalculatorEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_email_list(self, db_session):
        """Empty email list should return inactive/unconfirmed."""
        calculator = RenewalCalculator(db_session)

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=[],
                email_contents=[],
                extraction_metadata=None,
            )
        )

        assert renewal_date is None
        assert is_active is False
        assert trial_status is None
        assert is_confirmed is False

    def test_no_billing_cycle(self, db_session):
        """Missing billing cycle should still calculate based on patterns."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        email_dates = [now, now - timedelta(days=30)]
        email_contents = [
            "Your next payment will be on January 15, 2026",
            "Previous email",
        ]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle=None,  # No billing cycle provided
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        # Should extract from pattern even without billing cycle
        assert renewal_date is not None
        assert is_active is True

    def test_past_renewal_date_in_pattern(self, db_session):
        """Renewal date in the past should be adjusted forward."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        # Use 800 days to ensure >2 yearly cycles (800/365 = 2.19 cycles)
        email_dates = [now - timedelta(days=800), now - timedelta(days=830)]
        # Old pattern with past date
        email_contents = [
            "Your next payment will be on January 15, 2024",  # Past date
            "Previous email",
        ]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="yearly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        # Should fall back to billing cycle calculation
        # And should be inactive due to >2 cycles
        assert is_active is False

    def test_no_pattern_match_uses_billing_cycle(self, db_session):
        """No pattern match should fall back to billing cycle calculation."""
        calculator = RenewalCalculator(db_session)

        now = datetime.now(timezone.utc)
        last_email = now - timedelta(days=25)
        email_dates = [last_email, last_email - timedelta(days=30)]
        # No renewal date patterns in content
        email_contents = ["Thank you for your subscription", "Welcome to our service"]

        renewal_date, is_active, trial_status, is_confirmed = (
            calculator.calculate_renewal_info(
                provider="TestProvider",
                billing_cycle="monthly",
                email_dates=email_dates,
                email_contents=email_contents,
                extraction_metadata=None,
            )
        )

        assert renewal_date is not None  # Calculated from billing cycle
        assert is_active is True
        # Should be ~1 month from last email
        expected = last_email + relativedelta(months=1)
        assert abs((renewal_date - expected).days) <= 1


class TestRenewalCalculatorHelperFunctions:
    """Test helper functions and utilities."""

    def test_get_subscription_emails_function(
        self, db_session, test_subscription, test_email
    ):
        """Test the get_subscription_emails helper function."""
        from app.services.renewal_calculator import get_subscription_emails

        # Link the email to the subscription
        from app.models.email_message import subscription_emails

        db_session.execute(
            subscription_emails.insert().values(
                subscription_id=test_subscription.id, email_id=test_email.id
            )
        )
        db_session.commit()

        # Get subscription emails
        emails = get_subscription_emails(db_session, test_subscription.id)

        assert len(emails) == 1
        assert emails[0]["body_text"] == test_email.body_text
        assert "date" in emails[0]
        assert "body_html" in emails[0]
