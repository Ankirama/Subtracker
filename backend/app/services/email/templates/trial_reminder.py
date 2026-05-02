"""Trial-ending reminder email template.

Migrated verbatim from ``tasks/trial_reminders.py::send_trial_email``.
HTML and plain-text bodies are byte-identical to the previous inline strings.
"""

from __future__ import annotations

from datetime import date


def generate_trial_reminder_email(
    *,
    subscription_id: object,
    provider: str,
    amount: float,
    currency: str,
    billing_cycle: str,
    trial_end_date: date,
    days_until: int,
) -> tuple[str, str]:
    """Build (html_content, plain_content) for a trial-ending reminder.

    Args:
        subscription_id: Subscription primary key (used in deep-link URL).
        provider: ``Subscription.provider``.
        amount / currency / billing_cycle: Charge applied if the trial converts.
        trial_end_date: ``Subscription.trial_end_date``.
        days_until: Days between today and ``trial_end_date`` (clamped at >= 0).

    Returns:
        Tuple of (html_content, plain_content).
    """
    if days_until == 0:
        urgency = "TODAY"
        urgency_style = "background-color: #e53e3e; color: white;"
    elif days_until == 1:
        urgency = "TOMORROW"
        urgency_style = "background-color: #ed8936; color: white;"
    else:
        urgency = f"IN {days_until} DAYS"
        urgency_style = "background-color: #f6ad55; color: white;"

    days_plural = "s" if days_until != 1 else ""

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Urgent Warning Banner -->
        <div style="{urgency_style} padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 24px;">⚠️ TRIAL ENDING {urgency}</h1>
        </div>

        <div style="background-color: #fff; border: 2px solid #e53e3e; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">🔔 Important: Avoid Unexpected Charges</h2>
            <p style="font-size: 16px; color: #34495e;">
                Your <strong>{provider}</strong> free trial is ending soon.
                If you don't cancel before the trial ends, you'll be automatically charged.
            </p>
        </div>

        <div style="background-color: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="color: #2c3e50; margin-top: 0;">Trial Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Service:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">{provider}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Trial Ends:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">
                        <strong style="color: #e53e3e;">{trial_end_date.strftime('%B %d, %Y')}</strong> ({days_until} days)
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Charge After Trial:</strong></td>
                    <td style="padding: 10px 0; text-align: right; color: #e74c3c; font-size: 20px;">
                        <strong>{currency} {amount:.2f}</strong> / {billing_cycle}
                    </td>
                </tr>
            </table>
        </div>

        <div style="background-color: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #856404;">💡 What You Need To Do</h3>
            <div style="color: #856404;">
                <p style="margin: 10px 0;"><strong>If you want to keep this subscription:</strong></p>
                <ul style="margin: 5px 0;">
                    <li>No action needed - you'll be charged automatically</li>
                    <li>Amount: {currency} {amount:.2f} per {billing_cycle}</li>
                </ul>

                <p style="margin: 15px 0 10px 0;"><strong>If you want to cancel:</strong></p>
                <ul style="margin: 5px 0;">
                    <li>Cancel <strong>before {trial_end_date.strftime('%B %d, %Y')}</strong></li>
                    <li>Visit {provider}'s website to cancel</li>
                    <li>You have {days_until} day{days_plural} remaining</li>
                </ul>
            </div>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="http://localhost:5173/subscriptions/{subscription_id}"
               style="background-color: #e53e3e; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 16px;">
                View Subscription Details
            </a>
        </div>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
            <p style="margin: 0; color: #666; font-size: 14px;">
                📊 Track all your trials and subscriptions in one place<br>
                Never get surprised by unexpected charges again
            </p>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #95a5a6; font-size: 12px;">
            <p>
                You're receiving this trial reminder to help you avoid unexpected charges.<br>
                <a href="http://localhost:5173/notifications/settings" style="color: #3498db;">Manage notification settings</a>
            </p>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
⚠️ TRIAL ENDING {urgency}

Your {provider} free trial is ending soon!

Trial Details:
- Service: {provider}
- Trial Ends: {trial_end_date.strftime('%B %d, %Y')} ({days_until} days)
- Charge After Trial: {currency} {amount:.2f} per {billing_cycle}

WHAT YOU NEED TO DO:

If you want to keep this subscription:
• No action needed - you'll be charged automatically
• Amount: {currency} {amount:.2f} per {billing_cycle}

If you want to cancel:
• Cancel BEFORE {trial_end_date.strftime('%B %d, %Y')}
• Visit {provider}'s website to cancel
• You have {days_until} day{days_plural} remaining

View subscription: http://localhost:5173/subscriptions/{subscription_id}
Manage settings: http://localhost:5173/notifications/settings

---
Subscription Tracker - Never get surprised by unexpected charges
    """

    return html_content, plain_content
