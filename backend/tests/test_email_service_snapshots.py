"""Snapshot tests for the 3 inline HTML templates migrated from EmailService.

These tests lock the HTML output of the renewal_reminder, weekly_summary,
and monthly_summary templates that were extracted from
``services/email_service.py`` into ``services/email/templates/`` during
C1 Phase 5.

The structural anchor + exact length-fingerprint values were captured against
the PRE-migration code. Both pre- and post-migration outputs are byte-identical
(verified during Commit 2 of the migration), so these fingerprints continue
to lock the canonical output.

Each test compares:
1. A set of structural anchors (DOCTYPE, content blocks, key user-facing strings).
2. The exact length of the rendered HTML to detect any change in whitespace
   or template body. The length is asserted as an exact integer fingerprint.

If the rendered HTML changes, both the structural anchors and the length will
need to be updated. This is intentional — it forces a deliberate review of any
template change.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from app.services.email.templates.monthly_summary import generate_monthly_summary
from app.services.email.templates.renewal_reminder import generate_renewal_reminder
from app.services.email.templates.weekly_summary import generate_weekly_summary


# ---------------------------------------------------------------------------
# Renewal reminder
# ---------------------------------------------------------------------------


class TestRenewalReminderTemplateSnapshot:
    """Snapshot for ``app.services.email.templates.renewal_reminder.generate_renewal_reminder``."""

    FIXED_RENEWAL_DATE = datetime(2026, 5, 15, 12, 0, 0)

    def _render(self) -> str:
        return generate_renewal_reminder(
            user_name="Alice",
            subscription_name="Netflix",
            renewal_date=self.FIXED_RENEWAL_DATE,
            amount=15.99,
            currency="USD",
            days_until_renewal=7,
        )

    def test_structural_anchors(self):
        html = self._render()

        # DOCTYPE / framing
        assert "<!DOCTYPE html>" in html
        assert "<title>Renewal Reminder</title>" in html
        assert "</html>" in html

        # User-facing strings
        assert "Hi Alice," in html
        assert "<strong>Netflix</strong>" in html
        assert "<strong>7 days</strong>" in html
        assert "May 15, 2026" in html
        assert "USD 15.99" in html

        # Layout pieces
        assert "📊 Subscription Tracker" in html
        assert "⏰ Renewal Reminder" in html
        assert 'href="https://subscriptionstracker.io/subscriptions"' in html

    def test_length_fingerprint(self):
        """Exact length fingerprint — any whitespace/template change breaks this."""
        html = self._render()
        # Lock the canonical output length (matches pre-migration EmailService).
        assert len(html) == 3721, f"Renewal reminder HTML length changed: {len(html)}"


# ---------------------------------------------------------------------------
# Weekly summary
# ---------------------------------------------------------------------------


class TestWeeklySummaryTemplateSnapshot:
    """Snapshot for ``app.services.email.templates.weekly_summary.generate_weekly_summary``."""

    SUBSCRIPTIONS = [
        {"name": "Netflix", "amount": 15.99},
        {"name": "Spotify", "amount": 9.99},
        {"name": "Adobe CC", "amount": 54.99},
    ]
    UPCOMING = [
        {"name": "Disney+", "days_until": 3},
        {"name": "GitHub Pro", "days_until": 5},
    ]

    def _render(self, *, with_renewals: bool = True) -> str:
        return generate_weekly_summary(
            user_name="Bob",
            total_spent=80.97,
            currency="USD",
            subscriptions=self.SUBSCRIPTIONS,
            upcoming_renewals=self.UPCOMING if with_renewals else [],
        )

    def test_structural_anchors_with_renewals(self):
        html = self._render(with_renewals=True)

        assert "<!DOCTYPE html>" in html
        assert "<title>Weekly Summary</title>" in html
        assert "Hi Bob," in html
        assert "Total Spent This Week" in html
        assert "USD 80.97" in html

        # Subscriptions listed (top 5)
        assert "Netflix" in html
        assert "Spotify" in html
        assert "Adobe CC" in html
        assert "USD 15.99" in html
        assert "USD 9.99" in html
        assert "USD 54.99" in html

        # Upcoming renewals section present
        assert "⏰ Upcoming Renewals" in html
        assert "Disney+" in html
        assert "3 days" in html
        assert "GitHub Pro" in html
        assert "5 days" in html

        # CTA
        assert 'href="https://subscriptionstracker.io/analytics"' in html

    def test_omits_renewals_when_empty(self):
        html = self._render(with_renewals=False)

        # Header still present
        assert "<title>Weekly Summary</title>" in html
        # The renewals section title MUST be absent when list is empty
        assert "⏰ Upcoming Renewals" not in html

    def test_length_fingerprint_with_renewals(self):
        html = self._render(with_renewals=True)
        assert len(html) == 4713, f"Weekly summary HTML length changed: {len(html)}"

    def test_length_fingerprint_without_renewals(self):
        html = self._render(with_renewals=False)
        assert (
            len(html) == 4153
        ), f"Weekly summary (no renewals) HTML length changed: {len(html)}"


# ---------------------------------------------------------------------------
# Monthly summary
# ---------------------------------------------------------------------------


class TestMonthlySummaryTemplateSnapshot:
    """Snapshot for ``app.services.email.templates.monthly_summary.generate_monthly_summary``."""

    SUBSCRIPTIONS = [
        {"name": "Netflix", "amount": 15.99},
        {"name": "Adobe CC", "amount": 54.99},
        {"name": "Spotify", "amount": 9.99},
    ]
    SPENDING = {"streaming": 25.98, "tools": 54.99}
    COMPARISON = {"total": 100.0}

    # Fixed "now" so the 'datetime.now().strftime(...)' inside the template
    # produces a deterministic month/year header.
    FIXED_NOW = datetime(2026, 4, 15, 9, 30, 0)

    def _render(self, *, with_comparison: bool = True) -> str:
        with patch("app.services.email.templates.monthly_summary.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            # Preserve other datetime uses (none here, but defensive)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            return generate_monthly_summary(
                user_name="Carol",
                total_spent=120.97,
                currency="USD",
                subscriptions=self.SUBSCRIPTIONS,
                spending_breakdown=self.SPENDING,
                comparison_last_month=self.COMPARISON if with_comparison else None,
            )

    def test_structural_anchors_with_comparison(self):
        html = self._render(with_comparison=True)

        assert "<!DOCTYPE html>" in html
        assert "<title>Monthly Summary</title>" in html
        assert "Hi Carol," in html
        assert "April 2026" in html
        assert "Total Spent This Month" in html
        assert "USD 120.97" in html

        # Sorted by amount desc, top 10 (we have 3) - Adobe CC first
        # Order is verified by index check
        netflix_idx = html.find("Netflix")
        adobe_idx = html.find("Adobe CC")
        spotify_idx = html.find("Spotify")
        # Adobe CC has highest amount -> appears first
        assert adobe_idx < netflix_idx
        assert netflix_idx < spotify_idx

        # Comparison section present (positive diff: 120.97 - 100.0 = +20.97)
        assert "📈" in html
        assert "+USD 20.97" in html
        assert "vs last month" in html

    def test_omits_comparison_when_none(self):
        html = self._render(with_comparison=False)

        assert "<title>Monthly Summary</title>" in html
        # The comparison div must be absent
        assert "vs last month" not in html
        assert "📈" not in html
        assert "📉" not in html

    def test_length_fingerprint_with_comparison(self):
        html = self._render(with_comparison=True)
        assert len(html) == 4703, f"Monthly summary HTML length changed: {len(html)}"

    def test_length_fingerprint_without_comparison(self):
        html = self._render(with_comparison=False)
        assert (
            len(html) == 4172
        ), f"Monthly summary (no comparison) HTML length changed: {len(html)}"
