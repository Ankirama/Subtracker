"""Subscription-renewal reminder email template (Celery-task variant).

Migrated verbatim from ``tasks/renewal_reminders.py::send_renewal_email``.
HTML and plain-text bodies are byte-identical to the previous inline strings.

Note: this is *distinct* from
``services.email.templates.renewal_reminder.generate_renewal_reminder``,
which is the polished template called by ``services/notification_service.py``.
The two paths render different layouts and are kept separate to preserve
existing user-visible behaviour. Consolidating them is tracked separately.
"""

from __future__ import annotations

from datetime import date


def generate_subscription_renewal_alert(
    *,
    subscription_id: object,
    provider: str,
    amount: float,
    currency: str,
    billing_cycle: str,
    renewal_date: date,
    days_until: int,
) -> tuple[str, str]:
    """Build (html_content, plain_content) for the Celery renewal-reminder email.

    Args:
        subscription_id: Subscription primary key (used in the deep-link URL).
        provider / amount / currency / billing_cycle: Subscription fields.
        renewal_date: Next renewal date.
        days_until: Days from today to ``renewal_date``.

    Returns:
        Tuple of (html_content, plain_content).
    """
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">🔔 Renewal Reminder</h2>
            <p style="font-size: 16px; color: #34495e;">
                Your <strong>{provider}</strong> subscription will renew soon.
            </p>
        </div>

        <div style="background-color: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="color: #2c3e50; margin-top: 0;">Subscription Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Provider:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">{provider}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Amount:</strong></td>
                    <td style="padding: 10px 0; text-align: right; color: #e74c3c; font-size: 18px;">
                        <strong>{currency} {amount:.2f}</strong>
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Billing Cycle:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">{billing_cycle.capitalize()}</td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Renewal Date:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">
                        <strong>{renewal_date.strftime('%B %d, %Y')}</strong> ({days_until} days)
                    </td>
                </tr>
            </table>
        </div>

        <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
            <p style="margin: 0; color: #856404;">
                💡 <strong>Reminder:</strong> You have {days_until} days to cancel or modify this subscription if needed.
            </p>
        </div>

        <div style="text-align: center; margin-top: 30px;">
            <a href="http://localhost:5173/subscriptions/{subscription_id}"
               style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                View Subscription
            </a>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #95a5a6; font-size: 12px;">
            <p>
                You're receiving this because you have renewal reminders enabled.<br>
                <a href="http://localhost:5173/notifications/settings" style="color: #3498db;">Manage notification settings</a>
            </p>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
Renewal Reminder

Your {provider} subscription will renew in {days_until} days.

Subscription Details:
- Provider: {provider}
- Amount: {currency} {amount:.2f}
- Billing Cycle: {billing_cycle.capitalize()}
- Renewal Date: {renewal_date.strftime('%B %d, %Y')}

You have {days_until} days to cancel or modify this subscription if needed.

View subscription: http://localhost:5173/subscriptions/{subscription_id}
Manage settings: http://localhost:5173/notifications/settings
    """

    return html_content, plain_content
