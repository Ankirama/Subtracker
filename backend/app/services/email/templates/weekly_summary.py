"""Weekly subscription summary email template.

Migrated from ``services/email_service.py:_get_weekly_summary_template``.
HTML output is byte-identical (verified via ``test_email_service_snapshots.py``
length-fingerprint tests).
"""

from __future__ import annotations

from typing import List


def generate_weekly_summary(
    user_name: str,
    total_spent: float,
    currency: str,
    subscriptions: List[dict],
    upcoming_renewals: List[dict],
) -> str:
    """Get HTML template for weekly summary."""

    # Build subscription list HTML
    subs_html = ""
    for sub in subscriptions[:5]:  # Show top 5
        subs_html += f"""
            <div class="detail-row">
                <span class="detail-label">{sub['name']}</span>
                <span class="detail-value">{currency} {sub['amount']:.2f}</span>
            </div>
            """

    # Build upcoming renewals HTML
    renewals_html = ""
    for renewal in upcoming_renewals[:3]:  # Show next 3
        renewals_html += f"""
            <div class="detail-row">
                <span class="detail-label">{renewal['name']}</span>
                <span class="detail-value">{renewal['days_until']} days</span>
            </div>
            """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Summary</title>
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
        .summary-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            text-align: center;
            margin: 20px 0;
        }}
        .summary-amount {{
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .summary-label {{
            font-size: 16px;
            opacity: 0.9;
        }}
        .section {{
            margin: 30px 0;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #333;
        }}
        .details {{
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
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
            font-weight: 500;
            color: #666;
        }}
        .detail-value {{
            color: #333;
            font-weight: 600;
        }}
        .button {{
            display: inline-block;
            padding: 12px 30px;
            background-color: #3182ce;
            color: #ffffff;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
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
        <p>Here's your weekly subscription summary.</p>

        <div class="summary-box">
            <div class="summary-label">Total Spent This Week</div>
            <div class="summary-amount">{currency} {total_spent:.2f}</div>
        </div>

        <div class="section">
            <div class="section-title">📋 Active Subscriptions ({len(subscriptions)})</div>
            <div class="details">
                {subs_html}
            </div>
        </div>

        {f'''
        <div class="section">
            <div class="section-title">⏰ Upcoming Renewals</div>
            <div class="details">
                {renewals_html}
            </div>
        </div>
        ''' if upcoming_renewals else ''}

        <center>
            <a href="https://subscriptionstracker.io/analytics" class="button">View Full Analytics</a>
        </center>

        <div class="footer">
            <p>This is your weekly summary from Subscription Tracker.</p>
            <p>You can manage your notification preferences in your account settings.</p>
        </div>
    </div>
</body>
</html>
        """
