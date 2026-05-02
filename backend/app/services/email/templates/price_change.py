"""Price-change notification email template.

Migrated verbatim from ``tasks/price_change_monitor.py::send_price_change_email``.
HTML and plain-text bodies are byte-identical to the previous inline strings.
"""

from __future__ import annotations

from decimal import Decimal


def generate_price_change_email(
    *,
    subscription_id: object,
    provider: str,
    currency: str,
    billing_cycle: str,
    old_price: Decimal,
    new_price: Decimal,
    price_diff: Decimal,
    change_percent: float,
    is_increase: bool,
) -> tuple[str, str]:
    """Build (html_content, plain_content) for a price-change alert.

    Args:
        subscription_id: Subscription primary key (used in deep-link URL).
        provider: ``Subscription.provider``.
        currency / billing_cycle: Charge metadata.
        old_price / new_price / price_diff / change_percent: Pre-computed
            price-change figures from the notification metadata.
        is_increase: ``True`` for price increase, ``False`` for decrease.

    Returns:
        Tuple of (html_content, plain_content).
    """
    if is_increase:
        change_color = "#e53e3e"
        change_icon = "📈"
        change_word = "Increased"
        banner_style = "background-color: #fed7d7; border: 2px solid #fc8181;"
    else:
        change_color = "#38a169"
        change_icon = "📉"
        change_word = "Decreased"
        banner_style = "background-color: #c6f6d5; border: 2px solid #68d391;"

    sign = "+" if is_increase else ""

    advice_html = (
        "<p><strong>Price went up</strong> - Consider these options:</p>"
        if is_increase
        else "<p><strong>Good news!</strong> Price decreased:</p>"
    )
    advice_items_html = (
        "<li>Review if the service still provides good value</li>"
        "<li>Check if there are alternative plans available</li>"
        "<li>Consider canceling if the price is too high</li>"
        "<li>Look for competitor services with better pricing</li>"
        if is_increase
        else "<li>Enjoy the savings on your subscription</li>"
        "<li>Your next bill will reflect the lower price</li>"
        "<li>No action needed - this is good news!</li>"
    )

    advice_plain_header = (
        "PRICE INCREASE - Consider:" if is_increase else "PRICE DECREASE - Good news!"
    )
    advice_plain_body = (
        """• Review if the service still provides good value
• Check if there are alternative plans available
• Consider canceling if the price is too high
• Look for competitor services"""
        if is_increase
        else """• Enjoy the savings on your subscription
• Your next bill will reflect the lower price
• No action needed - this is good news!"""
    )

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Price Change Banner -->
        <div style="{banner_style} padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 24px; color: {change_color};">
                {change_icon} PRICE {change_word.upper()}
            </h1>
        </div>

        <div style="background-color: #fff; border: 2px solid {change_color}; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">💰 {provider} Price Update</h2>
            <p style="font-size: 16px; color: #34495e;">
                The subscription price for <strong>{provider}</strong> has changed.
            </p>
        </div>

        <div style="background-color: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="color: #2c3e50; margin-top: 0;">Price Comparison</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Previous Price:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">
                        <span style="text-decoration: line-through; color: #95a5a6;">
                            {currency} {old_price:.2f}
                        </span>
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>New Price:</strong></td>
                    <td style="padding: 10px 0; text-align: right; color: {change_color}; font-size: 20px;">
                        <strong>{currency} {new_price:.2f}</strong>
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Change:</strong></td>
                    <td style="padding: 10px 0; text-align: right; color: {change_color};">
                        <strong>{sign}{currency} {price_diff:.2f} ({change_percent:.1f}%)</strong>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px 0; color: #7f8c8d;"><strong>Billing Cycle:</strong></td>
                    <td style="padding: 10px 0; text-align: right;">{billing_cycle.capitalize()}</td>
                </tr>
            </table>
        </div>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #2c3e50;">💡 What You Can Do</h3>
            <div style="color: #495057;">
                {advice_html}
                <ul style="margin: 10px 0;">
                    {advice_items_html}
                </ul>
            </div>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="http://localhost:5173/subscriptions/{subscription_id}"
               style="background-color: {change_color}; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 16px;">
                View Subscription Details
            </a>
        </div>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
            <p style="margin: 0; color: #666; font-size: 14px;">
                📊 Track all your subscription price changes in one place<br>
                Stay informed about your recurring costs
            </p>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #95a5a6; font-size: 12px;">
            <p>
                You're receiving this price change alert to help you manage your subscriptions.<br>
                <a href="http://localhost:5173/notifications/settings" style="color: #3498db;">Manage notification settings</a>
            </p>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
{change_icon} PRICE {change_word.upper()}

Your {provider} subscription price has changed!

Price Comparison:
- Previous Price: {currency} {old_price:.2f}
- New Price: {currency} {new_price:.2f}
- Change: {sign}{currency} {price_diff:.2f} ({change_percent:.1f}%)
- Billing Cycle: {billing_cycle.capitalize()}

{advice_plain_header}
{advice_plain_body}

View subscription: http://localhost:5173/subscriptions/{subscription_id}
Manage settings: http://localhost:5173/notifications/settings

---
Subscription Tracker - Stay informed about your recurring costs
    """

    return html_content, plain_content
