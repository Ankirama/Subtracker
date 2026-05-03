"""
Intelligent review suggestions service.
Analyzes subscriptions and suggests which ones users should review or cancel.
"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timedelta, date, timezone
from typing import List, Dict, Optional
from uuid import UUID
from collections import defaultdict

from app.models.subscription import Subscription
from app.schemas.cancellation import (
    ReviewSuggestion,
    ReviewSuggestionReason,
    ReviewSuggestionsResponse,
)
import logging

logger = logging.getLogger(__name__)


def _ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert naive datetime to timezone-aware (UTC) if needed.

    SQLite doesn't preserve timezone info, so datetimes may be naive.
    This ensures consistent comparison with timezone-aware datetimes.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReviewSuggestionsService:
    """
    Service for generating intelligent subscription review suggestions.

    Analyzes subscriptions using multiple heuristics:
    - Trial ending detection (critical priority)
    - Unused subscription detection (no recent emails)
    - Price increase detection (if we have historical data)
    - Expensive + unused combination
    - Duplicate provider detection
    """

    def __init__(self, db: Session):
        """
        Initialize review suggestions service.

        Args:
            db: Database session
        """
        self.db = db

    def get_review_suggestions(
        self, user_id: UUID, include_dismissed: bool = False
    ) -> ReviewSuggestionsResponse:
        """
        Get all review suggestions for a user's subscriptions.

        Args:
            user_id: User UUID to analyze
            include_dismissed: Include previously dismissed suggestions

        Returns:
            ReviewSuggestionsResponse with categorized suggestions
        """
        logger.info(f"Generating review suggestions for user {user_id}")

        suggestions = []

        # Get all active subscriptions for user
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.is_active,
            Subscription.cancellation_status != "cancelled",
        )
        subscriptions = self.db.execute(stmt).scalars().all()

        if not subscriptions:
            logger.info(f"No active subscriptions found for user {user_id}")
            return ReviewSuggestionsResponse(
                suggestions=[], total_count=0, critical_count=0, high_priority_count=0
            )

        # Run all detection methods
        trial_suggestions = self._detect_trial_ending(subscriptions)
        unused_suggestions = self._detect_likely_unused(subscriptions)
        duplicate_suggestions = self._detect_duplicates(subscriptions)
        expensive_unused_suggestions = self._detect_expensive_unused(subscriptions)
        pending_cancellation_suggestions = self._detect_pending_cancellation(
            subscriptions
        )

        # Combine all suggestions (avoiding duplicates)
        all_suggestions = (
            trial_suggestions
            + unused_suggestions
            + duplicate_suggestions
            + expensive_unused_suggestions
            + pending_cancellation_suggestions
        )

        # Remove duplicate suggestions (same subscription, prioritize higher severity)
        suggestions_map: Dict[UUID, ReviewSuggestion] = {}
        priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        for suggestion in all_suggestions:
            sub_id = suggestion.subscription_id
            if sub_id not in suggestions_map:
                suggestions_map[sub_id] = suggestion
            else:
                # Keep the higher priority suggestion
                current_priority = priority_order.get(suggestion.priority, 0)
                existing_priority = priority_order.get(
                    suggestions_map[sub_id].priority, 0
                )
                if current_priority > existing_priority:
                    suggestions_map[sub_id] = suggestion

        suggestions = list(suggestions_map.values())

        # Sort by priority (critical first, then high, medium, low)
        def sort_key(s):
            priority_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            return (
                priority_map.get(s.priority, 4),
                s.action_by_date if s.action_by_date else datetime.max,
            )

        suggestions.sort(key=sort_key)

        # Count by priority
        critical_count = sum(1 for s in suggestions if s.priority == "critical")
        high_priority_count = sum(1 for s in suggestions if s.priority == "high")

        logger.info(
            f"Generated {len(suggestions)} suggestions for user {user_id}: "
            f"{critical_count} critical, {high_priority_count} high priority"
        )

        return ReviewSuggestionsResponse(
            suggestions=suggestions,
            total_count=len(suggestions),
            critical_count=critical_count,
            high_priority_count=high_priority_count,
        )

    def _detect_trial_ending(
        self, subscriptions: List[Subscription]
    ) -> List[ReviewSuggestion]:
        """
        Detect subscriptions with trials ending soon.

        Critical: Trial ends today or tomorrow
        High: Trial ends within 7 days

        Args:
            subscriptions: List of subscriptions to analyze

        Returns:
            List of trial ending suggestions
        """
        suggestions = []
        today = date.today()

        for sub in subscriptions:
            if not sub.trial_end_date or sub.trial_status not in (
                "trial",
                "trial_ending",
            ):
                continue

            days_until_end = (sub.trial_end_date - today).days

            # Skip if trial already ended
            if days_until_end < 0:
                continue

            # Critical: Trial ends today or within 1 day
            if days_until_end <= 1:
                reason = ReviewSuggestionReason.TRIAL_ENDING
                priority = "critical"
                if days_until_end == 0:
                    message = f"🚨 Your {sub.provider} trial ends TODAY! Cancel now to avoid charges."
                else:
                    message = f"⚠️ Your {sub.provider} trial ends TOMORROW! Cancel now to avoid charges."
                action_by = datetime.combine(sub.trial_end_date, datetime.min.time())

            # High: Trial ends within 7 days
            elif days_until_end <= 7:
                reason = ReviewSuggestionReason.TRIAL_ENDING_SOON
                priority = "high"
                message = f"Your {sub.provider} trial ends in {days_until_end} days. Review before you're charged."
                action_by = datetime.combine(sub.trial_end_date, datetime.min.time())

            else:
                # Trial ends >7 days from now, not urgent
                continue

            suggestions.append(
                ReviewSuggestion(
                    subscription_id=sub.id,
                    provider=sub.provider or "Unknown",
                    amount=float(sub.amount) if sub.amount else None,
                    currency=sub.currency,
                    billing_cycle=sub.billing_cycle,
                    reason=reason,
                    priority=priority,
                    message=message,
                    action_by_date=action_by,
                )
            )

        logger.info(f"Found {len(suggestions)} trial ending suggestions")
        return suggestions

    def _detect_likely_unused(
        self, subscriptions: List[Subscription]
    ) -> List[ReviewSuggestion]:
        """
        Detect subscriptions that appear unused (no recent emails).

        Medium: No emails in last 30 days
        Low: No emails in last 60 days but had some activity

        Args:
            subscriptions: List of subscriptions to analyze

        Returns:
            List of unused subscription suggestions
        """
        suggestions = []
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        now - timedelta(days=60)

        for sub in subscriptions:
            # Skip if we don't have email tracking
            if not sub.source_emails:
                continue

            # Get most recent email date
            recent_emails = [
                email
                for email in sub.source_emails
                if email.date and _ensure_timezone_aware(email.date) > thirty_days_ago
            ]

            if not recent_emails:
                # No emails in last 30 days
                # Check if we have ANY emails
                all_emails_sorted = sorted(
                    [e for e in sub.source_emails if e.date],
                    key=lambda x: x.date,
                    reverse=True,
                )

                if all_emails_sorted:
                    last_email_date = _ensure_timezone_aware(all_emails_sorted[0].date)
                    days_since = (now - last_email_date).days

                    # Calculate monthly cost for impact messaging
                    monthly_cost = self._calculate_monthly_cost(sub)
                    cost_msg = f" (${monthly_cost:.2f}/month)" if monthly_cost else ""

                    suggestions.append(
                        ReviewSuggestion(
                            subscription_id=sub.id,
                            provider=sub.provider or "Unknown",
                            amount=float(sub.amount) if sub.amount else None,
                            currency=sub.currency,
                            billing_cycle=sub.billing_cycle,
                            reason=ReviewSuggestionReason.LIKELY_UNUSED,
                            priority="medium",
                            message=f"No activity from {sub.provider} in {days_since} days{cost_msg}. Still using it?",
                            action_by_date=None,
                            days_since_last_email=days_since,
                        )
                    )

        logger.info(f"Found {len(suggestions)} unused subscription suggestions")
        return suggestions

    def _detect_expensive_unused(
        self, subscriptions: List[Subscription]
    ) -> List[ReviewSuggestion]:
        """
        Detect expensive subscriptions with no recent activity.

        High: Cost >$20/month + no emails in 30 days

        Args:
            subscriptions: List of subscriptions to analyze

        Returns:
            List of expensive unused suggestions
        """
        suggestions = []
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        for sub in subscriptions:
            # Calculate monthly cost
            monthly_cost = self._calculate_monthly_cost(sub)

            # Skip if not expensive (threshold: $20/month)
            if not monthly_cost or monthly_cost < 20.0:
                continue

            # Check for recent emails
            recent_emails = (
                [
                    email
                    for email in sub.source_emails
                    if email.date
                    and _ensure_timezone_aware(email.date) > thirty_days_ago
                ]
                if sub.source_emails
                else []
            )

            if not recent_emails:
                days_since = None
                if sub.source_emails:
                    all_emails_sorted = sorted(
                        [e for e in sub.source_emails if e.date],
                        key=lambda x: x.date,
                        reverse=True,
                    )
                    if all_emails_sorted:
                        days_since = (
                            now - _ensure_timezone_aware(all_emails_sorted[0].date)
                        ).days

                suggestions.append(
                    ReviewSuggestion(
                        subscription_id=sub.id,
                        provider=sub.provider or "Unknown",
                        amount=float(sub.amount) if sub.amount else None,
                        currency=sub.currency,
                        billing_cycle=sub.billing_cycle,
                        reason=ReviewSuggestionReason.EXPENSIVE_UNUSED,
                        priority="high",
                        message=(
                            f"💰 {sub.provider} costs ${monthly_cost:.2f}/month "
                            "but shows no recent activity. Consider cancelling?"
                        ),
                        action_by_date=None,
                        days_since_last_email=days_since,
                    )
                )

        logger.info(f"Found {len(suggestions)} expensive unused suggestions")
        return suggestions

    def _detect_duplicates(
        self, subscriptions: List[Subscription]
    ) -> List[ReviewSuggestion]:
        """
        Detect multiple subscriptions to the same provider.

        Medium: 2+ active subscriptions to same provider

        Args:
            subscriptions: List of subscriptions to analyze

        Returns:
            List of duplicate provider suggestions
        """
        suggestions = []

        # Group by provider (case-insensitive)
        provider_groups = defaultdict(list)
        for sub in subscriptions:
            if sub.provider:
                provider_groups[sub.provider.lower()].append(sub)

        # Find providers with multiple subscriptions
        for provider_key, subs in provider_groups.items():
            if len(subs) <= 1:
                continue

            # We have duplicates!
            provider_name = subs[0].provider  # Use original case

            # Calculate total cost
            total_monthly_cost = sum(
                self._calculate_monthly_cost(sub) or 0 for sub in subs
            )

            # Create suggestion for each duplicate subscription
            for sub in subs:
                sub_cost = self._calculate_monthly_cost(sub)
                cost_msg = f" (${sub_cost:.2f}/month)" if sub_cost else ""

                suggestions.append(
                    ReviewSuggestion(
                        subscription_id=sub.id,
                        provider=sub.provider or "Unknown",
                        amount=float(sub.amount) if sub.amount else None,
                        currency=sub.currency,
                        billing_cycle=sub.billing_cycle,
                        reason=ReviewSuggestionReason.DUPLICATE_DETECTED,
                        priority="medium",
                        message=(
                            f"You have {len(subs)} active {provider_name} subscriptions{cost_msg}. "
                            f"Total: ${total_monthly_cost:.2f}/month. Do you need them all?"
                        ),
                        action_by_date=None,
                    )
                )

        logger.info(f"Found {len(suggestions)} duplicate provider suggestions")
        return suggestions

    def _detect_pending_cancellation(
        self, subscriptions: List[Subscription]
    ) -> List[ReviewSuggestion]:
        """
        Surface subscriptions where the sync pipeline auto-created a
        cancellation suggestion that the user hasn't acted on yet.

        These rows have ``suggested_cancellation_status`` populated but
        their effective ``cancellation_status`` is still ``active`` —
        meaning the AI saw a cancellation email but the user hasn't
        clicked Accept or Dismiss on the subscription detail banner.

        High priority: action is straightforward (one click) and delaying
        leaves the subscription on books that should be marked cancelled.

        Args:
            subscriptions: List of subscriptions to analyze

        Returns:
            List of pending cancellation review suggestions
        """
        suggestions = []

        for sub in subscriptions:
            if not sub.suggested_cancellation_status:
                continue

            reason_text = (
                sub.cancellation_suggestion_reason
                or "An email looked like a cancellation confirmation."
            )
            message = (
                f"AI detected a cancellation email for {sub.provider}. "
                f"{reason_text} Confirm on the subscription page to mark "
                "it as cancelled, or dismiss if it's a false positive."
            )

            suggestions.append(
                ReviewSuggestion(
                    subscription_id=sub.id,
                    provider=sub.provider or "Unknown",
                    amount=float(sub.amount) if sub.amount else None,
                    currency=sub.currency,
                    billing_cycle=sub.billing_cycle,
                    reason=ReviewSuggestionReason.CANCELLATION_DETECTED,
                    priority="high",
                    message=message,
                    action_by_date=None,
                )
            )

        logger.info(f"Found {len(suggestions)} pending cancellation suggestions")
        return suggestions

    def _calculate_monthly_cost(self, subscription: Subscription) -> Optional[float]:
        """
        Calculate monthly cost for a subscription regardless of billing cycle.

        Args:
            subscription: Subscription to calculate cost for

        Returns:
            Monthly cost in float or None
        """
        if not subscription.amount:
            return None

        amount = float(subscription.amount)
        cycle = subscription.billing_cycle.lower()

        # Convert to monthly cost
        cycle_map = {
            "weekly": amount * 4.33,  # Average weeks per month
            "monthly": amount,
            "quarterly": amount / 3,
            "biannual": amount / 6,
            "yearly": amount / 12,
            "annual": amount / 12,
        }

        return cycle_map.get(cycle, amount)


async def generate_review_suggestions(
    user_id: UUID, db: Session, include_dismissed: bool = False
) -> ReviewSuggestionsResponse:
    """
    Convenience function to generate review suggestions.

    Args:
        user_id: User UUID
        db: Database session
        include_dismissed: Include dismissed suggestions

    Returns:
        ReviewSuggestionsResponse with all suggestions
    """
    service = ReviewSuggestionsService(db)
    return service.get_review_suggestions(user_id, include_dismissed)
