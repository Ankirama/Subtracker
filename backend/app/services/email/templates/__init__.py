"""Email templates package — facade and direct exports.

The ``EmailTemplates`` class is a thin facade that preserves the public
API exposed by the legacy ``services/email_templates.py`` (which is now
a backward-compat shim). New code should prefer importing the module-level
functions directly:

    from app.services.email.templates.summary import generate_summary_email
    from app.services.email.templates.renewal_reminder import generate_renewal_reminder

The facade also exposes ``_render_*`` static helpers for the summary email
because some tests (``test_email_templates.py::TestRenderHelpers``) call
them directly.
"""

from __future__ import annotations

from app.services.email.templates import summary
from app.services.email.templates.monthly_summary import generate_monthly_summary
from app.services.email.templates.otp_2fa import generate_2fa_otp_email
from app.services.email.templates.renewal_reminder import generate_renewal_reminder
from app.services.email.templates.summary import generate_summary_email
from app.services.email.templates.verification import generate_email_verification_email
from app.services.email.templates.weekly_summary import generate_weekly_summary


class EmailTemplates:
    """Facade preserving the legacy ``services/email_templates.EmailTemplates`` API.

    All methods are static and dispatch to module-level functions in the
    submodules of ``app.services.email.templates``.
    """

    # --- Outbound HTML templates (originally in services/email_templates.py) ---

    @staticmethod
    def generate_summary_email(summary_data, frontend_url="http://localhost:5173"):
        return generate_summary_email(summary_data, frontend_url)

    @staticmethod
    def generate_2fa_otp_email(user_name, otp_code, expires_in_minutes=10):
        return generate_2fa_otp_email(user_name, otp_code, expires_in_minutes)

    @staticmethod
    def generate_email_verification_email(user_name, verification_url):
        return generate_email_verification_email(user_name, verification_url)

    # --- Inline templates (originally in services/email_service.py) ---

    @staticmethod
    def generate_renewal_reminder(
        user_name,
        subscription_name,
        renewal_date,
        amount,
        currency,
        days_until_renewal,
    ):
        return generate_renewal_reminder(
            user_name,
            subscription_name,
            renewal_date,
            amount,
            currency,
            days_until_renewal,
        )

    @staticmethod
    def generate_weekly_summary(
        user_name, total_spent, currency, subscriptions, upcoming_renewals
    ):
        return generate_weekly_summary(
            user_name, total_spent, currency, subscriptions, upcoming_renewals
        )

    @staticmethod
    def generate_monthly_summary(
        user_name,
        total_spent,
        currency,
        subscriptions,
        spending_breakdown,
        comparison_last_month=None,
    ):
        return generate_monthly_summary(
            user_name,
            total_spent,
            currency,
            subscriptions,
            spending_breakdown,
            comparison_last_month,
        )

    # --- Private render helpers used by tests/test_email_templates.py ---

    @staticmethod
    def _render_insights(insights):
        return summary.render_insights(insights)

    @staticmethod
    def _render_changes(summary_data):
        return summary.render_changes(summary_data)

    @staticmethod
    def _render_top_categories(top_categories):
        return summary.render_top_categories(top_categories)

    @staticmethod
    def _render_top_subscriptions(top_subscriptions):
        return summary.render_top_subscriptions(top_subscriptions)

    @staticmethod
    def _render_ai_insights(ai_insights):
        return summary.render_ai_insights(ai_insights)

    @staticmethod
    def _render_ai_recommendations(recommendations, potential_savings):
        return summary.render_ai_recommendations(recommendations, potential_savings)

    @staticmethod
    def _render_upcoming_renewals(upcoming_renewals):
        return summary.render_upcoming_renewals(upcoming_renewals)


__all__ = [
    "EmailTemplates",
    "generate_summary_email",
    "generate_2fa_otp_email",
    "generate_email_verification_email",
    "generate_renewal_reminder",
    "generate_weekly_summary",
    "generate_monthly_summary",
]
