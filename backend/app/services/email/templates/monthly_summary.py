"""Monthly subscription summary email template.

Migrated from ``services/email_service.py:_get_monthly_summary_template``.
HTML output is byte-identical (verified via ``test_email_service_snapshots.py``
length-fingerprint tests).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional


def generate_monthly_summary(
    user_name: str,
    total_spent: float,
    currency: str,
    subscriptions: List[dict],
    spending_breakdown: dict,
    comparison_last_month: Optional[dict] = None,
) -> str:
    """Get HTML template for monthly summary."""

    # Build subscription list HTML
    subs_html = ""
    for sub in sorted(subscriptions, key=lambda x: x.get("amount", 0), reverse=True)[
        :10
    ]:
        subs_html += f"""
            <div class="detail-row">
                <span class="detail-label">{sub['name']}</span>
                <span class="detail-value">{currency} {sub['amount']:.2f}</span>
            </div>
            """

    # Build comparison HTML if available
    comparison_html = ""
    if comparison_last_month:
        diff = total_spent - comparison_last_month.get("total", 0)
        diff_percent = (
            (diff / comparison_last_month.get("total", 1)) * 100
            if comparison_last_month.get("total", 0) > 0
            else 0
        )
        trend_emoji = "📈" if diff > 0 else "📉"
        trend_color = "#e53e3e" if diff > 0 else "#38a169"

        comparison_html = f"""
            <div class="comparison-box" style="background-color: #f0f4f8; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <div style="text-align: center;">
                    <span style="font-size: 24px;">{trend_emoji}</span>
                    <div style="font-size: 20px; font-weight: bold; color: {trend_color}; margin: 10px 0;">
                        {'+' if diff > 0 else ''}{currency} {diff:.2f} ({'+' if diff > 0 else ''}{diff_percent:.1f}%)
                    </div>
                    <div style="color: #666;">vs last month</div>
                </div>
            </div>
            """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monthly Summary</title>
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
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 40px;
            border-radius: 8px;
            text-align: center;
            margin: 20px 0;
        }}
        .summary-amount {{
            font-size: 42px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .summary-label {{
            font-size: 18px;
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
        <p>Here's your monthly subscription summary for {datetime.now().strftime('%B %Y')}.</p>

        <div class="summary-box">
            <div class="summary-label">Total Spent This Month</div>
            <div class="summary-amount">{currency} {total_spent:.2f}</div>
        </div>

        {comparison_html}

        <div class="section">
            <div class="section-title">💰 Top Subscriptions</div>
            <div class="details">
                {subs_html}
            </div>
        </div>

        <center>
            <a href="https://subscriptionstracker.io/analytics" class="button">View Detailed Analytics</a>
        </center>

        <div class="footer">
            <p>This is your monthly summary from Subscription Tracker.</p>
            <p>You can manage your notification preferences in your account settings.</p>
        </div>
    </div>
</body>
</html>
        """
