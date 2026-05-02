"""Budget alert email template.

Migrated verbatim from ``tasks/budget_alerts.py::send_budget_alert_email``.
HTML and plain-text bodies are byte-identical to the previous inline strings.
"""

from __future__ import annotations

from typing import Optional


def generate_budget_alert_email(
    *,
    budget_name: str,
    budget_category: Optional[str],
    alert_type: str,
    message: str,
    currency: str,
    current_spending: float,
    limit_amount: float,
    remaining: float,
    percentage_used: float,
    period_start: object,
    period_end: object,
) -> tuple[str, str]:
    """Build (html_content, plain_content) for a budget alert.

    Args:
        budget_name: ``Budget.name``.
        budget_category: ``Budget.category`` (may be None/empty).
        alert_type: "warning" or "exceeded".
        message: Human-readable alert sentence.
        currency / current_spending / limit_amount / remaining / percentage_used:
            Snapshot fields from ``BudgetService.get_budget_status``.
        period_start / period_end: Period boundaries (rendered with ``str()``;
            previously inlined as bare ``date``/``datetime``).

    Returns:
        Tuple of (html_content, plain_content).
    """
    urgency_color = "#F59E0B" if alert_type == "warning" else "#EF4444"
    urgency_text = "Approaching Limit" if alert_type == "warning" else "Over Budget"
    remaining_color = "#EF4444" if remaining < 0 else "#10B981"

    category_html = (
        f'<p style="color: #6b7280; margin: 20px 0;"><strong>Category:</strong> {budget_category.capitalize()}</p>'
        if budget_category
        else ""
    )

    html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {urgency_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0; font-size: 24px;">⚠️ Budget Alert</h2>
                <p style="margin: 10px 0 0 0; font-size: 16px;">{urgency_text}</p>
            </div>

            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px;">
                <h3 style="color: #333; margin-top: 0;">Budget: {budget_name}</h3>

                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
                                <strong>Current Spending:</strong>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e5e7eb; text-align: right;">
                                {currency} {current_spending:.2f}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
                                <strong>Budget Limit:</strong>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e5e7eb; text-align: right;">
                                {currency} {limit_amount:.2f}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
                                <strong>Remaining:</strong>
                            </td>
                            <td style="padding: 10px 0; border-bottom: 1px solid #e5e7eb; text-align: right; color: {remaining_color};">
                                {currency} {remaining:.2f}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0;">
                                <strong>Usage:</strong>
                            </td>
                            <td style="padding: 10px 0; text-align: right; color: {urgency_color};">
                                <strong>{percentage_used:.1f}%</strong>
                            </td>
                        </tr>
                    </table>
                </div>

                <div style="background-color: #FEF3C7; border-left: 4px solid #F59E0B; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <p style="margin: 0; color: #92400E;">
                        <strong>Alert Details:</strong><br>
                        {message}
                    </p>
                </div>

                {category_html}

                <p style="color: #6b7280; margin: 20px 0;">
                    <strong>Period:</strong> {period_start} to {period_end}
                </p>

                <div style="text-align: center; margin-top: 30px;">
                    <a href="http://localhost:5173/budgets"
                       style="background-color: #3B82F6; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        View Budget Details
                    </a>
                </div>

                <p style="color: #9ca3af; font-size: 12px; margin-top: 30px; text-align: center;">
                    You can adjust your budget settings or disable alerts in your budget preferences.
                </p>
            </div>
        </div>
        """

    category_plain = "Category: " + budget_category if budget_category else ""

    plain_content = f"""
Budget Alert: {budget_name}

{urgency_text}

Current Spending: {currency} {current_spending:.2f}
Budget Limit: {currency} {limit_amount:.2f}
Remaining: {currency} {remaining:.2f}
Usage: {percentage_used:.1f}%

{message}

{category_plain}
Period: {period_start} to {period_end}

View your budget details: http://localhost:5173/budgets
        """

    return html_content, plain_content
