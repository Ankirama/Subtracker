"""Renewal reminder email template.

Migrated from ``services/email_service.py:_get_renewal_reminder_template``.
HTML output is byte-identical (verified via ``test_email_service_snapshots.py``
length-fingerprint tests).
"""

from __future__ import annotations

from datetime import datetime


def generate_renewal_reminder(
    user_name: str,
    subscription_name: str,
    renewal_date: datetime,
    amount: float,
    currency: str,
    days_until_renewal: int,
) -> str:
    """Get HTML template for renewal reminder."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Renewal Reminder</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: #ffffff;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #3182ce;
        }}
        .alert-box {{
            background-color: #fff5e6;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .details {{
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin: 20px 0;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e9ecef;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            font-weight: 600;
            color: #666;
        }}
        .detail-value {{
            color: #333;
        }}
        .amount {{
            font-size: 24px;
            font-weight: bold;
            color: #3182ce;
        }}
        .button {{
            display: inline-block;
            padding: 12px 30px;
            background-color: #3182ce;
            color: #ffffff;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
            text-align: center;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">📊 Subscription Tracker</div>
        </div>

        <h2>Hi {user_name},</h2>

        <div class="alert-box">
            <strong>⏰ Renewal Reminder</strong><br>
            Your <strong>{subscription_name}</strong> subscription will renew in <strong>{days_until_renewal} days</strong>.
        </div>

        <div class="details">
            <div class="detail-row">
                <span class="detail-label">Subscription</span>
                <span class="detail-value">{subscription_name}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Renewal Date</span>
                <span class="detail-value">{renewal_date.strftime('%B %d, %Y')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Amount</span>
                <span class="detail-value amount">{currency} {amount:.2f}</span>
            </div>
        </div>

        <p>If you wish to cancel or modify this subscription, please log in to your account.</p>

        <center>
            <a href="https://subscriptionstracker.io/subscriptions" class="button">View Subscription</a>
        </center>

        <div class="footer">
            <p>This is an automated reminder from Subscription Tracker.</p>
            <p>You can manage your notification preferences in your account settings.</p>
        </div>
    </div>
</body>
</html>
        """
