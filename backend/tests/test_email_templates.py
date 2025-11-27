"""Comprehensive tests for email_templates"""

import pytest

from app.services.email_templates import EmailTemplates


@pytest.fixture
def full_summary_data():
    """Create comprehensive summary data for testing"""
    return {
        "period_type": "weekly",
        "start_date": "January 01, 2024",
        "end_date": "January 07, 2024",
        "user_name": "John Doe",
        "total_subscriptions": 5,
        "total_monthly_cost": 49.95,
        "total_yearly_cost": 599.40,
        "new_subscriptions_count": 2,
        "new_subscriptions": [
            {"provider": "Netflix", "amount": 15.99, "billing_cycle": "monthly"},
            {"provider": "Spotify", "amount": 9.99, "billing_cycle": "monthly"},
        ],
        "cancelled_subscriptions_count": 1,
        "cancelled_subscriptions": [
            {"provider": "Adobe CC", "amount": 54.99, "billing_cycle": "monthly"}
        ],
        "top_categories": [
            {"category": "streaming", "count": 2, "cost": 25.98},
            {"category": "productivity", "count": 1, "cost": 14.99},
        ],
        "top_subscriptions": [
            {"provider": "Adobe CC", "monthly_cost": 54.99},
            {"provider": "Netflix", "monthly_cost": 15.99},
            {"provider": "Spotify", "monthly_cost": 9.99},
        ],
        "savings_from_cancellations": 54.99,
        "cost_of_new": 25.98,
        "net_change": -29.01,
        "upcoming_renewals": [
            {"provider": "Netflix", "renewal_date": "2024-01-15", "amount": 15.99},
            {"provider": "Spotify", "renewal_date": "2024-01-20", "amount": 9.99},
        ],
        "insights": [
            "📈 You added 2 net new subscriptions this period",
            "💰 You're spending €49.95/month on subscriptions",
        ],
        "ai_recommendations": [
            {
                "type": "unused_subscription",
                "title": "Review Netflix subscription",
                "description": "No activity detected in 30 days",
                "priority": "high",
                "potential_savings": 15.99,
            },
            {
                "type": "family_plan_upgrade",
                "title": "Spotify Family Plan",
                "description": "Save money with family plan",
                "priority": "medium",
                "potential_savings": 5.00,
            },
        ],
        "ai_insights": [
            "You could save by consolidating streaming services",
            "Consider annual billing for Spotify",
        ],
        "potential_savings": 20.99,
        "total_ai_recommendations": 2,
    }


@pytest.fixture
def empty_summary_data():
    """Create minimal/empty summary data"""
    return {
        "period_type": "monthly",
        "start_date": "January 01, 2024",
        "end_date": "January 31, 2024",
        "user_name": "Jane",
        "total_subscriptions": 0,
        "total_monthly_cost": 0,
        "total_yearly_cost": 0,
        "new_subscriptions_count": 0,
        "new_subscriptions": [],
        "cancelled_subscriptions_count": 0,
        "cancelled_subscriptions": [],
        "top_categories": [],
        "top_subscriptions": [],
        "savings_from_cancellations": 0,
        "cost_of_new": 0,
        "net_change": 0,
        "upcoming_renewals": [],
        "insights": [],
        "ai_recommendations": [],
        "ai_insights": [],
        "potential_savings": 0.0,
        "total_ai_recommendations": 0,
    }


class TestGenerateSummaryEmail:
    """Tests for generate_summary_email method"""

    def test_generates_complete_email_with_full_data(self, full_summary_data):
        """Should generate complete HTML email with all sections"""
        html = EmailTemplates.generate_summary_email(full_summary_data)

        # Basic structure
        assert "<!DOCTYPE html>" in html
        assert '<html lang="en">' in html
        assert "</html>" in html

        # Header content
        assert "Weekly Subscription Summary" in html
        assert "Hi John Doe!" in html
        assert "January 01, 2024" in html
        assert "January 07, 2024" in html

        # Stats
        assert "5" in html  # total subscriptions
        assert "€49.95" in html  # monthly cost
        assert "2" in html  # new subscriptions
        assert "1" in html  # cancelled

        # Sections
        assert "Netflix" in html
        assert "Spotify" in html
        assert "Adobe CC" in html

    def test_handles_empty_data_gracefully(self, empty_summary_data):
        """Should generate valid HTML even with empty data"""
        html = EmailTemplates.generate_summary_email(empty_summary_data)

        # Basic structure still present
        assert "<!DOCTYPE html>" in html
        assert "Monthly Subscription Summary" in html
        assert "Hi Jane!" in html

        # Empty values handled
        assert "€0" in html

        # No error sections should be present
        assert "undefined" not in html.lower()
        # Note: 'none' appears in CSS (text-decoration: none), so we don't check for it

    def test_includes_insights_section(self, full_summary_data):
        """Should include insights when provided"""
        html = EmailTemplates.generate_summary_email(full_summary_data)

        assert "💡 Key Insights" in html
        assert "📈 You added 2 net new subscriptions" in html
        assert "💰 You're spending €49.95/month" in html

    def test_includes_ai_sections(self, full_summary_data):
        """Should include AI insights and recommendations"""
        html = EmailTemplates.generate_summary_email(full_summary_data)

        # AI Insights
        assert "🤖 AI Optimization Insights" in html
        assert "consolidating streaming services" in html

        # AI Recommendations
        assert "💡 AI-Powered Recommendations" in html
        assert "💰 Potential Savings" in html
        assert "€20.99/month" in html
        assert "Review Netflix subscription" in html

    def test_includes_changes_section(self, full_summary_data):
        """Should show new and cancelled subscriptions"""
        html = EmailTemplates.generate_summary_email(full_summary_data)

        assert "📋 Changes This Period" in html
        assert "✅ New Subscriptions" in html
        assert "❌ Cancelled Subscriptions" in html
        assert "Netflix" in html
        assert "Adobe CC" in html

    def test_includes_categories_section(self, full_summary_data):
        """Should show top spending categories"""
        html = EmailTemplates.generate_summary_email(full_summary_data)

        assert "📊 Top Spending Categories" in html
        assert "Streaming" in html  # Title-cased from streaming
        assert "€25.98/mo" in html

    def test_includes_top_subscriptions_section(self, full_summary_data):
        """Should show most expensive subscriptions"""
        html = EmailTemplates.generate_summary_email(full_summary_data)

        assert "💰 Most Expensive Subscriptions" in html
        assert "Adobe CC" in html
        assert "€54.99/mo" in html

    def test_includes_upcoming_renewals_section(self, full_summary_data):
        """Should show upcoming renewal dates"""
        html = EmailTemplates.generate_summary_email(full_summary_data)

        assert "🔔 Upcoming Renewals" in html
        assert "Netflix" in html
        assert "Jan 15, 2024" in html

    def test_period_type_capitalization(self):
        """Should capitalize period type correctly"""
        data = {
            "period_type": "weekly",
            "user_name": "Test",
            "start_date": "Jan 1",
            "end_date": "Jan 7",
            "total_subscriptions": 0,
            "total_monthly_cost": 0,
            "new_subscriptions_count": 0,
            "cancelled_subscriptions_count": 0,
            "new_subscriptions": [],
            "cancelled_subscriptions": [],
            "top_categories": [],
            "top_subscriptions": [],
            "upcoming_renewals": [],
            "insights": [],
            "net_change": 0,
        }

        html = EmailTemplates.generate_summary_email(data)
        assert "Weekly Subscription Summary" in html


class TestGenerate2FAOTPEmail:
    """Tests for generate_2fa_otp_email method"""

    def test_generates_complete_otp_email(self):
        """Should generate complete OTP email"""
        html = EmailTemplates.generate_2fa_otp_email(
            user_name="Alice", otp_code="123456", expires_in_minutes=10
        )

        # Basic structure
        assert "<!DOCTYPE html>" in html
        assert "Two-Factor Authentication" in html

        # User content
        assert "Hi Alice!" in html
        assert "123456" in html
        assert "⏱️ Expires in 10 minutes" in html

        # Security notice
        assert "🛡️ Security Notice" in html
        assert "never share this code" in html.lower()

    def test_handles_custom_expiration_time(self):
        """Should handle custom expiration times"""
        html = EmailTemplates.generate_2fa_otp_email(
            user_name="Bob", otp_code="654321", expires_in_minutes=5
        )

        assert "⏱️ Expires in 5 minutes" in html

    def test_includes_otp_code_prominently(self):
        """Should display OTP code prominently"""
        html = EmailTemplates.generate_2fa_otp_email(
            user_name="Charlie", otp_code="999888", expires_in_minutes=10
        )

        # OTP should be in a prominent location
        assert '<div class="otp-code">999888</div>' in html
        assert "Verification Code" in html

    def test_includes_security_warnings(self):
        """Should include security warnings"""
        html = EmailTemplates.generate_2fa_otp_email(
            user_name="Dave", otp_code="111222", expires_in_minutes=10
        )

        assert "single-use only" in html
        assert "case-sensitive" in html
        assert "didn't attempt to log in" in html


class TestGenerateEmailVerificationEmail:
    """Tests for generate_email_verification_email method"""

    def test_generates_complete_verification_email(self):
        """Should generate complete verification email"""
        html = EmailTemplates.generate_email_verification_email(
            user_name="Eve", verification_url="https://example.com/verify/abc123"
        )

        # Basic structure
        assert "<!DOCTYPE html>" in html
        assert "Welcome to SubTracker!" in html

        # User content
        assert "Hi Eve!" in html
        assert "🎉 Thank you for signing up!" in html

        # Verification link
        assert "https://example.com/verify/abc123" in html
        assert "Complete your Registration" in html

    def test_includes_verification_url_twice(self):
        """Should include URL as button and as text"""
        url = "https://example.com/verify/token123"
        html = EmailTemplates.generate_email_verification_email(
            user_name="Frank", verification_url=url
        )

        # Should appear at least twice (button and text link)
        assert html.count(url) >= 2
        assert f'<a href="{url}" class="verify-button">' in html

    def test_includes_expiration_notice(self):
        """Should mention link expiration"""
        html = EmailTemplates.generate_email_verification_email(
            user_name="Grace", verification_url="https://example.com/verify/xyz"
        )

        assert "24 hours" in html
        assert "expires" in html.lower()
        assert "only be used once" in html

    def test_includes_safety_message(self):
        """Should include message for non-registrants"""
        html = EmailTemplates.generate_email_verification_email(
            user_name="Henry", verification_url="https://example.com/verify/123"
        )

        assert "didn't create an account" in html
        assert "safely ignore" in html


class TestRenderHelpers:
    """Tests for private rendering helper methods"""

    def test_render_insights_with_content(self):
        """Should render insights when provided"""
        insights = ["📈 Growing trend", "💰 Spending insight", "🎯 Recommendation"]

        html = EmailTemplates._render_insights(insights)

        assert "💡 Key Insights" in html
        assert "📈 Growing trend" in html
        assert "💰 Spending insight" in html
        assert "🎯 Recommendation" in html

    def test_render_insights_returns_empty_for_no_data(self):
        """Should return empty string when no insights"""
        html = EmailTemplates._render_insights([])
        assert html == ""

    def test_render_changes_with_new_and_cancelled(self):
        """Should render both new and cancelled subscriptions"""
        summary_data = {
            "new_subscriptions": [
                {"provider": "Netflix", "amount": 15.99, "billing_cycle": "monthly"}
            ],
            "cancelled_subscriptions": [
                {"provider": "Hulu", "amount": 12.99, "billing_cycle": "monthly"}
            ],
            "net_change": 3.00,
        }

        html = EmailTemplates._render_changes(summary_data)

        assert "📋 Changes This Period" in html
        assert "✅ New Subscriptions" in html
        assert "Netflix" in html
        assert "❌ Cancelled Subscriptions" in html
        assert "Hulu" in html
        assert "increased" in html
        assert "€3.00" in html

    def test_render_changes_returns_empty_for_no_changes(self):
        """Should return empty string when no changes"""
        summary_data = {"new_subscriptions": [], "cancelled_subscriptions": []}

        html = EmailTemplates._render_changes(summary_data)
        assert html == ""

    def test_render_changes_shows_decrease(self):
        """Should show decrease when net_change is negative"""
        summary_data = {
            "new_subscriptions": [],
            "cancelled_subscriptions": [
                {"provider": "Adobe", "amount": 54.99, "billing_cycle": "monthly"}
            ],
            "net_change": -54.99,
        }

        html = EmailTemplates._render_changes(summary_data)

        assert "decreased" in html
        assert "€54.99" in html

    def test_render_top_categories_with_data(self):
        """Should render top categories"""
        categories = [
            {"category": "streaming", "count": 3, "cost": 45.97},
            {"category": "productivity_tools", "count": 2, "cost": 29.98},
        ]

        html = EmailTemplates._render_top_categories(categories)

        assert "📊 Top Spending Categories" in html
        assert "Streaming" in html  # Title cased
        assert "Productivity Tools" in html  # Underscore replaced, title cased
        assert "€45.97/mo" in html
        assert "3 subscriptions" in html
        assert "2 subscriptions" in html

    def test_render_top_categories_singular_subscription(self):
        """Should use singular 'subscription' for count of 1"""
        categories = [{"category": "news", "count": 1, "cost": 9.99}]

        html = EmailTemplates._render_top_categories(categories)

        assert "1 subscription" in html
        assert "1 subscriptions" not in html

    def test_render_top_categories_returns_empty_for_no_data(self):
        """Should return empty string when no categories"""
        html = EmailTemplates._render_top_categories([])
        assert html == ""

    def test_render_top_subscriptions_with_data(self):
        """Should render top subscriptions"""
        subscriptions = [
            {"provider": "Adobe CC", "monthly_cost": 54.99},
            {"provider": "Netflix", "monthly_cost": 15.99},
        ]

        html = EmailTemplates._render_top_subscriptions(subscriptions)

        assert "💰 Most Expensive Subscriptions" in html
        assert "Adobe CC" in html
        assert "€54.99/mo" in html
        assert "Netflix" in html
        assert "€15.99/mo" in html

    def test_render_top_subscriptions_returns_empty_for_no_data(self):
        """Should return empty string when no subscriptions"""
        html = EmailTemplates._render_top_subscriptions([])
        assert html == ""

    def test_render_ai_insights_with_data(self):
        """Should render AI insights"""
        insights = ["Consider consolidating services", "Switch to annual billing"]

        html = EmailTemplates._render_ai_insights(insights)

        assert "🤖 AI Optimization Insights" in html
        assert "Consider consolidating services" in html
        assert "Switch to annual billing" in html

    def test_render_ai_insights_returns_empty_for_no_data(self):
        """Should return empty string when no AI insights"""
        html = EmailTemplates._render_ai_insights([])
        assert html == ""

    def test_render_ai_recommendations_with_data(self):
        """Should render AI recommendations with savings"""
        recommendations = [
            {
                "type": "unused_subscription",
                "title": "Cancel unused Netflix",
                "description": "No activity in 60 days",
                "priority": "high",
                "potential_savings": 15.99,
            },
            {
                "type": "family_plan_upgrade",
                "title": "Upgrade to family plan",
                "description": "Share with family",
                "priority": "medium",
                "potential_savings": 5.00,
            },
        ]

        html = EmailTemplates._render_ai_recommendations(recommendations, 20.99)

        assert "💡 AI-Powered Recommendations" in html
        assert "💰 Potential Savings" in html
        assert "€20.99/month" in html
        assert "Cancel unused Netflix" in html
        assert "Save €15.99/mo" in html
        assert "HIGH" in html
        assert "MEDIUM" in html

    def test_render_ai_recommendations_handles_many_recommendations(self):
        """Should show only top 5 and mention remaining"""
        recommendations = [
            {
                "type": "test",
                "title": f"Rec {i}",
                "description": "Test",
                "priority": "low",
                "potential_savings": 1.0,
            }
            for i in range(10)
        ]

        html = EmailTemplates._render_ai_recommendations(recommendations, 10.0)

        assert "+ 5 more recommendations" in html

    def test_render_ai_recommendations_priority_colors(self):
        """Should use correct colors for priorities"""
        recommendations = [
            {
                "type": "test",
                "title": "High",
                "description": "Test",
                "priority": "high",
                "potential_savings": 10.0,
            },
            {
                "type": "test",
                "title": "Medium",
                "description": "Test",
                "priority": "medium",
                "potential_savings": 5.0,
            },
            {
                "type": "test",
                "title": "Low",
                "description": "Test",
                "priority": "low",
                "potential_savings": 1.0,
            },
        ]

        html = EmailTemplates._render_ai_recommendations(recommendations, 16.0)

        # Check for priority badges
        assert "HIGH" in html
        assert "MEDIUM" in html
        assert "LOW" in html

    def test_render_ai_recommendations_returns_empty_for_no_data(self):
        """Should return empty string when no recommendations"""
        html = EmailTemplates._render_ai_recommendations([], 0.0)
        assert html == ""

    def test_render_upcoming_renewals_with_data(self):
        """Should render upcoming renewals with dates"""
        renewals = [
            {"provider": "Netflix", "renewal_date": "2024-01-15", "amount": 15.99},
            {"provider": "Spotify", "renewal_date": "2024-01-20", "amount": 9.99},
        ]

        html = EmailTemplates._render_upcoming_renewals(renewals)

        assert "🔔 Upcoming Renewals" in html
        assert "Netflix" in html
        assert "Jan 15, 2024" in html
        assert "€15.99" in html
        assert "Spotify" in html
        assert "Jan 20, 2024" in html

    def test_render_upcoming_renewals_returns_empty_for_no_data(self):
        """Should return empty string when no renewals"""
        html = EmailTemplates._render_upcoming_renewals([])
        assert html == ""
