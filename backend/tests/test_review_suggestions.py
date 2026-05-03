"""Comprehensive tests for review_suggestions service"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta, date, timezone
from sqlalchemy.orm import Session

from app.services.review_suggestions import (
    ReviewSuggestionsService,
    generate_review_suggestions,
)
from app.models.subscription import Subscription
from app.models.email_message import EmailMessage
from app.models.user import User
from app.schemas.cancellation import ReviewSuggestionReason


@pytest.fixture
def review_service(db_session: Session) -> ReviewSuggestionsService:
    """Create ReviewSuggestionsService instance"""
    return ReviewSuggestionsService(db_session)


@pytest.fixture
def trial_ending_today(db_session: Session, test_user: User) -> Subscription:
    """Subscription with trial ending today"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Trial Today",
        amount=9.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        trial_status="trial_ending",
        trial_end_date=date.today(),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def trial_ending_tomorrow(db_session: Session, test_user: User) -> Subscription:
    """Subscription with trial ending tomorrow"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Trial Tomorrow",
        amount=14.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        trial_status="trial_ending",
        trial_end_date=date.today() + timedelta(days=1),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def trial_ending_week(db_session: Session, test_user: User) -> Subscription:
    """Subscription with trial ending in 5 days"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Trial Week",
        amount=19.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
        trial_status="trial",
        trial_end_date=date.today() + timedelta(days=5),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def unused_subscription(db_session: Session, test_user: User) -> Subscription:
    """Subscription with no recent email activity"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Unused Service",
        amount=9.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    # Create old email (45 days ago)
    old_email = EmailMessage(
        id=uuid4(),
        mailbox_id=uuid4(),
        message_id=f"msg-{str(uuid4())[:8]}",
        date=(datetime.utcnow() - timedelta(days=45)).replace(tzinfo=timezone.utc),
        sender="noreply@unused.com",
        recipient="user@example.com",
        subject="Old message",
    )
    db_session.add(old_email)
    sub.source_emails.append(old_email)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def expensive_unused(db_session: Session, test_user: User) -> Subscription:
    """Expensive subscription (>$20/month) with no recent activity"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Expensive Pro",
        amount=29.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    # Create old email (35 days ago)
    old_email = EmailMessage(
        id=uuid4(),
        mailbox_id=uuid4(),
        message_id=f"msg-{str(uuid4())[:8]}",
        date=(datetime.utcnow() - timedelta(days=35)).replace(tzinfo=timezone.utc),
        sender="noreply@expensive.com",
        recipient="user@example.com",
        subject="Old notification",
    )
    db_session.add(old_email)
    sub.source_emails.append(old_email)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def duplicate_subscriptions(db_session: Session, test_user: User):
    """Multiple subscriptions to same provider"""
    subs = []
    for i in range(3):
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Netflix",
            amount=15.99,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
        )
        db_session.add(sub)
        subs.append(sub)

    db_session.commit()
    for sub in subs:
        db_session.refresh(sub)
    return subs


@pytest.fixture
def active_subscription(db_session: Session, test_user: User) -> Subscription:
    """Subscription with recent email activity"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Active Service",
        amount=9.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    # Create recent email (5 days ago)
    recent_email = EmailMessage(
        id=uuid4(),
        mailbox_id=uuid4(),
        message_id=f"msg-{str(uuid4())[:8]}",
        date=(datetime.utcnow() - timedelta(days=5)).replace(tzinfo=timezone.utc),
        sender="noreply@active.com",
        recipient="user@example.com",
        subject="Recent message",
    )
    db_session.add(recent_email)
    sub.source_emails.append(recent_email)
    db_session.commit()
    db_session.refresh(sub)
    return sub


class TestGetReviewSuggestions:
    """Tests for get_review_suggestions method"""

    def test_returns_empty_for_no_subscriptions(
        self, review_service: ReviewSuggestionsService, test_user: User
    ):
        """Should return empty response when user has no subscriptions"""
        result = review_service.get_review_suggestions(test_user.id)

        assert result.total_count == 0
        assert result.critical_count == 0
        assert result.high_priority_count == 0
        assert len(result.suggestions) == 0

    def test_combines_all_suggestion_types(
        self,
        review_service: ReviewSuggestionsService,
        test_user: User,
        trial_ending_today: Subscription,
        unused_subscription: Subscription,
        expensive_unused: Subscription,
    ):
        """Should detect and combine multiple suggestion types"""
        result = review_service.get_review_suggestions(test_user.id)

        # Should have 3 suggestions: trial ending (critical), unused (medium), expensive unused (high)
        assert result.total_count == 3
        assert result.critical_count == 1
        assert result.high_priority_count == 1

    def test_sorts_by_priority(
        self,
        review_service: ReviewSuggestionsService,
        test_user: User,
        unused_subscription: Subscription,
        trial_ending_today: Subscription,
        expensive_unused: Subscription,
    ):
        """Should sort suggestions by priority: critical > high > medium > low"""
        result = review_service.get_review_suggestions(test_user.id)

        # Critical should be first
        assert result.suggestions[0].priority == "critical"
        assert result.suggestions[0].provider == "Trial Today"

        # High should be second
        assert result.suggestions[1].priority == "high"
        assert result.suggestions[1].provider == "Expensive Pro"

        # Medium should be third
        assert result.suggestions[2].priority == "medium"
        assert result.suggestions[2].provider == "Unused Service"

    def test_deduplicates_same_subscription(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should not create duplicate suggestions for same subscription"""
        # Create subscription that matches multiple criteria
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Multi-Criteria",
            amount=25.0,  # Expensive
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
        )
        db_session.add(sub)

        # Add old email to make it "unused"
        old_email = EmailMessage(
            id=uuid4(),
            message_id=f"msg-{str(uuid4())[:8]}",
            date=(datetime.utcnow() - timedelta(days=40)).replace(tzinfo=timezone.utc),
            sender="noreply@multi.com",
            recipient="user@example.com",
            subject="Old",
            mailbox_id=uuid4(),
        )
        db_session.add(old_email)
        sub.source_emails.append(old_email)
        db_session.commit()

        result = review_service.get_review_suggestions(test_user.id)

        # Should only have 1 suggestion (highest priority one)
        # Both "expensive_unused" (high) and "likely_unused" (medium) would match
        assert result.total_count == 1
        assert result.suggestions[0].priority == "high"  # Keep higher priority
        assert result.suggestions[0].subscription_id == sub.id


class TestDetectTrialEnding:
    """Tests for _detect_trial_ending method"""

    def test_detects_trial_ending_today(
        self, review_service: ReviewSuggestionsService, trial_ending_today: Subscription
    ):
        """Should detect trial ending today as critical"""
        suggestions = review_service._detect_trial_ending([trial_ending_today])

        assert len(suggestions) == 1
        assert suggestions[0].priority == "critical"
        assert suggestions[0].reason == ReviewSuggestionReason.TRIAL_ENDING
        assert "TODAY" in suggestions[0].message
        assert "🚨" in suggestions[0].message

    def test_detects_trial_ending_tomorrow(
        self,
        review_service: ReviewSuggestionsService,
        trial_ending_tomorrow: Subscription,
    ):
        """Should detect trial ending tomorrow as critical"""
        suggestions = review_service._detect_trial_ending([trial_ending_tomorrow])

        assert len(suggestions) == 1
        assert suggestions[0].priority == "critical"
        assert suggestions[0].reason == ReviewSuggestionReason.TRIAL_ENDING
        assert "TOMORROW" in suggestions[0].message
        assert "⚠️" in suggestions[0].message

    def test_detects_trial_ending_within_week(
        self, review_service: ReviewSuggestionsService, trial_ending_week: Subscription
    ):
        """Should detect trial ending within 7 days as high priority"""
        suggestions = review_service._detect_trial_ending([trial_ending_week])

        assert len(suggestions) == 1
        assert suggestions[0].priority == "high"
        assert suggestions[0].reason == ReviewSuggestionReason.TRIAL_ENDING_SOON
        assert "5 days" in suggestions[0].message

    def test_ignores_trials_ending_far_future(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should ignore trials ending >7 days from now"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Trial Future",
            amount=9.99,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
            trial_status="trial",
            trial_end_date=date.today() + timedelta(days=15),
        )
        db_session.add(sub)
        db_session.commit()

        suggestions = review_service._detect_trial_ending([sub])

        assert len(suggestions) == 0

    def test_ignores_expired_trials(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should ignore trials that already ended"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Trial Expired",
            amount=9.99,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
            trial_status="trial",
            trial_end_date=date.today() - timedelta(days=5),
        )
        db_session.add(sub)
        db_session.commit()

        suggestions = review_service._detect_trial_ending([sub])

        assert len(suggestions) == 0

    def test_ignores_non_trial_subscriptions(
        self,
        review_service: ReviewSuggestionsService,
        active_subscription: Subscription,
    ):
        """Should ignore subscriptions not in trial status"""
        suggestions = review_service._detect_trial_ending([active_subscription])

        assert len(suggestions) == 0


class TestDetectLikelyUnused:
    """Tests for _detect_likely_unused method"""

    def test_detects_subscription_with_no_recent_emails(
        self,
        review_service: ReviewSuggestionsService,
        unused_subscription: Subscription,
    ):
        """Should detect subscription with no emails in last 30 days"""
        suggestions = review_service._detect_likely_unused([unused_subscription])

        assert len(suggestions) == 1
        assert suggestions[0].priority == "medium"
        assert suggestions[0].reason == ReviewSuggestionReason.LIKELY_UNUSED
        assert "45 days" in suggestions[0].message
        assert suggestions[0].days_since_last_email == 45

    def test_ignores_subscriptions_with_recent_activity(
        self,
        review_service: ReviewSuggestionsService,
        active_subscription: Subscription,
    ):
        """Should ignore subscriptions with emails in last 30 days"""
        suggestions = review_service._detect_likely_unused([active_subscription])

        assert len(suggestions) == 0

    def test_ignores_subscriptions_without_email_tracking(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should ignore subscriptions with no email tracking"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="No Emails",
            amount=9.99,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        suggestions = review_service._detect_likely_unused([sub])

        assert len(suggestions) == 0

    def test_includes_monthly_cost_in_message(
        self,
        review_service: ReviewSuggestionsService,
        unused_subscription: Subscription,
    ):
        """Should include monthly cost in suggestion message"""
        suggestions = review_service._detect_likely_unused([unused_subscription])

        assert "$9.99/month" in suggestions[0].message


class TestDetectExpensiveUnused:
    """Tests for _detect_expensive_unused method"""

    def test_detects_expensive_subscription_with_no_activity(
        self, review_service: ReviewSuggestionsService, expensive_unused: Subscription
    ):
        """Should detect expensive (>$20) subscription with no recent emails"""
        suggestions = review_service._detect_expensive_unused([expensive_unused])

        assert len(suggestions) == 1
        assert suggestions[0].priority == "high"
        assert suggestions[0].reason == ReviewSuggestionReason.EXPENSIVE_UNUSED
        assert "💰" in suggestions[0].message
        assert "$29.99/month" in suggestions[0].message
        assert suggestions[0].days_since_last_email == 35

    def test_ignores_cheap_subscriptions(
        self,
        review_service: ReviewSuggestionsService,
        unused_subscription: Subscription,
    ):
        """Should ignore subscriptions under $20/month threshold"""
        # unused_subscription is only $9.99/month
        suggestions = review_service._detect_expensive_unused([unused_subscription])

        assert len(suggestions) == 0

    def test_ignores_expensive_with_recent_activity(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should ignore expensive subscriptions with recent emails"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Expensive Active",
            amount=29.99,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        # Add recent email
        recent_email = EmailMessage(
            id=uuid4(),
            message_id=f"msg-{str(uuid4())[:8]}",
            date=(datetime.utcnow() - timedelta(days=10)).replace(tzinfo=timezone.utc),
            sender="noreply@expensive.com",
            recipient="user@example.com",
            subject="Recent",
            mailbox_id=uuid4(),
        )
        db_session.add(recent_email)
        sub.source_emails.append(recent_email)
        db_session.commit()

        suggestions = review_service._detect_expensive_unused([sub])

        assert len(suggestions) == 0


class TestDetectDuplicates:
    """Tests for _detect_duplicates method"""

    def test_detects_duplicate_providers(
        self, review_service: ReviewSuggestionsService, duplicate_subscriptions
    ):
        """Should detect multiple subscriptions to same provider"""
        suggestions = review_service._detect_duplicates(duplicate_subscriptions)

        # Should create suggestion for each duplicate subscription
        assert len(suggestions) == 3
        assert all(s.priority == "medium" for s in suggestions)
        assert all(
            s.reason == ReviewSuggestionReason.DUPLICATE_DETECTED for s in suggestions
        )
        assert all("3 active Netflix subscriptions" in s.message for s in suggestions)

    def test_calculates_total_cost_for_duplicates(
        self, review_service: ReviewSuggestionsService, duplicate_subscriptions
    ):
        """Should calculate total monthly cost across duplicates"""
        suggestions = review_service._detect_duplicates(duplicate_subscriptions)

        # 3 subscriptions at $15.99 each = $47.97/month total
        assert all("$47.97/month" in s.message for s in suggestions)

    def test_ignores_single_subscriptions(
        self,
        review_service: ReviewSuggestionsService,
        active_subscription: Subscription,
    ):
        """Should not flag single subscription to a provider"""
        suggestions = review_service._detect_duplicates([active_subscription])

        assert len(suggestions) == 0

    def test_case_insensitive_provider_matching(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should match providers case-insensitively"""
        subs = []
        for provider_name in ["Netflix", "NETFLIX", "netflix"]:
            sub = Subscription(
                id=uuid4(),
                user_id=test_user.id,
                provider=provider_name,
                amount=15.99,
                currency="USD",
                billing_cycle="monthly",
                is_active=True,
            )
            db_session.add(sub)
            subs.append(sub)
        db_session.commit()

        suggestions = review_service._detect_duplicates(subs)

        # Should detect all 3 as duplicates
        assert len(suggestions) == 3


class TestDetectPendingCancellation:
    """Tests for _detect_pending_cancellation — surfaces AI-detected
    cancellation suggestions that the user hasn't acted on yet."""

    def test_returns_empty_when_no_suggestion_pending(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Sub without `suggested_cancellation_status` is ignored."""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Spotify",
            amount=9.99,
            currency="EUR",
            billing_cycle="monthly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        suggestions = review_service._detect_pending_cancellation([sub])

        assert suggestions == []

    def test_surfaces_pending_suggestion_with_high_priority(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Sub with `suggested_cancellation_status` set → one high-priority
        suggestion with reason CANCELLATION_DETECTED."""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Netflix",
            amount=15.99,
            currency="EUR",
            billing_cycle="monthly",
            is_active=True,
            suggested_cancellation_status="cancelled",
            cancellation_suggestion_reason="Email confirms cancellation.",
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()

        suggestions = review_service._detect_pending_cancellation([sub])

        assert len(suggestions) == 1
        s = suggestions[0]
        assert s.subscription_id == sub.id
        assert s.provider == "Netflix"
        assert s.reason == ReviewSuggestionReason.CANCELLATION_DETECTED
        assert s.priority == "high"
        assert "Netflix" in s.message
        assert "Email confirms cancellation." in s.message
        # No action_by_date — user can review at their leisure
        assert s.action_by_date is None

    def test_uses_default_message_when_reason_missing(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Defensive: a suggestion without a reason text still gets a
        useful message."""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="HBO",
            amount=12.99,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
            suggested_cancellation_status="cancelled",
            cancellation_suggestion_reason=None,
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()

        suggestions = review_service._detect_pending_cancellation([sub])

        assert len(suggestions) == 1
        # Default fallback message used
        assert "looked like a cancellation" in suggestions[0].message

    def test_appears_in_full_get_review_suggestions_response(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """End-to-end: pending cancellation suggestion shows up in the
        public ``get_review_suggestions`` response (not only the internal
        detector)."""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Disney+",
            amount=8.99,
            currency="EUR",
            billing_cycle="monthly",
            is_active=True,
            cancellation_status="active",
            suggested_cancellation_status="cancelled",
            cancellation_suggestion_reason="Cancellation confirmation email.",
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()

        response = review_service.get_review_suggestions(test_user.id)

        cancellation_suggestions = [
            s
            for s in response.suggestions
            if s.reason == ReviewSuggestionReason.CANCELLATION_DETECTED
        ]
        assert len(cancellation_suggestions) == 1
        assert cancellation_suggestions[0].provider == "Disney+"
        assert response.high_priority_count >= 1


class TestCalculateMonthlyCost:
    """Tests for _calculate_monthly_cost helper"""

    def test_calculates_weekly_cost(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should convert weekly to monthly (amount * 4.33)"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Weekly",
            amount=10.0,
            currency="USD",
            billing_cycle="weekly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        monthly_cost = review_service._calculate_monthly_cost(sub)
        assert monthly_cost == pytest.approx(43.3, rel=0.01)

    def test_calculates_monthly_cost(
        self,
        review_service: ReviewSuggestionsService,
        active_subscription: Subscription,
    ):
        """Should return same amount for monthly billing"""
        monthly_cost = review_service._calculate_monthly_cost(active_subscription)
        assert monthly_cost == 9.99

    def test_calculates_quarterly_cost(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should convert quarterly to monthly (amount / 3)"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Quarterly",
            amount=30.0,
            currency="USD",
            billing_cycle="quarterly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        monthly_cost = review_service._calculate_monthly_cost(sub)
        assert monthly_cost == pytest.approx(10.0, rel=0.01)

    def test_calculates_biannual_cost(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should convert biannual to monthly (amount / 6)"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Biannual",
            amount=60.0,
            currency="USD",
            billing_cycle="biannual",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        monthly_cost = review_service._calculate_monthly_cost(sub)
        assert monthly_cost == pytest.approx(10.0, rel=0.01)

    def test_calculates_yearly_cost(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should convert yearly to monthly (amount / 12)"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Yearly",
            amount=120.0,
            currency="USD",
            billing_cycle="yearly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        monthly_cost = review_service._calculate_monthly_cost(sub)
        assert monthly_cost == pytest.approx(10.0, rel=0.01)

    def test_handles_annual_alias(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should treat 'annual' same as 'yearly'"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Annual",
            amount=120.0,
            currency="USD",
            billing_cycle="annual",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        monthly_cost = review_service._calculate_monthly_cost(sub)
        assert monthly_cost == pytest.approx(10.0, rel=0.01)

    def test_returns_none_for_no_amount(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should return None if subscription has no amount"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="No Amount",
            amount=None,
            currency="USD",
            billing_cycle="monthly",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        monthly_cost = review_service._calculate_monthly_cost(sub)
        assert monthly_cost is None

    def test_handles_unknown_billing_cycle(
        self,
        review_service: ReviewSuggestionsService,
        db_session: Session,
        test_user: User,
    ):
        """Should default to original amount for unknown cycle"""
        sub = Subscription(
            id=uuid4(),
            user_id=test_user.id,
            provider="Unknown Cycle",
            amount=25.0,
            currency="USD",
            billing_cycle="unknown",
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        monthly_cost = review_service._calculate_monthly_cost(sub)
        assert monthly_cost == 25.0


@pytest.mark.asyncio
async def test_generate_review_suggestions_convenience_function(
    db_session: Session, test_user: User, trial_ending_today: Subscription
):
    """Should work through async convenience function"""
    result = await generate_review_suggestions(test_user.id, db_session)

    assert result.total_count >= 1
    assert result.critical_count >= 1
    assert isinstance(result.suggestions, list)
