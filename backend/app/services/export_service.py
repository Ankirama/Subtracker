"""
Export service for generating CSV and PDF reports of subscription data.
"""

import csv
import io
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal

from app.models.subscription import Subscription


class ExportService:
    """Service for exporting subscription data to various formats."""

    @staticmethod
    def _normalize_billing_to_monthly(amount: float, billing_cycle: str) -> float:
        """Convert any billing cycle to monthly equivalent."""
        if not amount:
            return 0.0

        cycle_multipliers = {
            "weekly": 4.33,
            "monthly": 1.0,
            "quarterly": 1 / 3,
            "biannual": 1 / 6,
            "yearly": 1 / 12,
            "annual": 1 / 12,
        }

        multiplier = cycle_multipliers.get(billing_cycle.lower(), 1.0)
        return round(amount * multiplier, 2)

    @staticmethod
    def generate_csv(
        subscriptions: List[Subscription],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> str:
        """
        Generate CSV export of subscriptions.

        Args:
            subscriptions: List of subscription objects to export
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header with metadata
        writer.writerow(["Subscription Export Report"])
        writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        if start_date:
            writer.writerow(["Start Date:", start_date.strftime("%Y-%m-%d")])
        if end_date:
            writer.writerow(["End Date:", end_date.strftime("%Y-%m-%d")])
        writer.writerow([])  # Empty row

        # Write column headers
        headers = [
            "Provider",
            "Amount",
            "Currency",
            "Billing Cycle",
            "Monthly Equivalent",
            "Renewal Date",
            "Next Renewal",
            "Category",
            "Status",
            "Custom Label",
            "Email Sender",
            "Confidence Score",
            "First Detected",
            "Last Updated",
            "Notes",
        ]
        writer.writerow(headers)

        # Write subscription data
        total_monthly = 0.0
        for sub in subscriptions:
            monthly_cost = ExportService._normalize_billing_to_monthly(
                float(sub.amount) if sub.amount else 0.0, sub.billing_cycle
            )
            total_monthly += monthly_cost

            row = [
                sub.provider,
                float(sub.amount) if sub.amount else "",
                sub.currency,
                sub.billing_cycle,
                monthly_cost,
                sub.renewal_date.strftime("%Y-%m-%d") if sub.renewal_date else "",
                (
                    sub.next_renewal_date.strftime("%Y-%m-%d")
                    if sub.next_renewal_date
                    else ""
                ),
                sub.category,
                "Active" if sub.is_active else "Inactive",
                sub.custom_label or "",
                sub.email_sender or "",
                f"{float(sub.confidence_score):.2f}" if sub.confidence_score else "",
                (
                    sub.first_detected_at.strftime("%Y-%m-%d")
                    if sub.first_detected_at
                    else ""
                ),
                sub.updated_at.strftime("%Y-%m-%d") if sub.updated_at else "",
                sub.notes or "",
            ]
            writer.writerow(row)

        # Write summary
        writer.writerow([])  # Empty row
        writer.writerow(["Summary"])
        writer.writerow(["Total Subscriptions:", len(subscriptions)])
        writer.writerow(
            ["Active Subscriptions:", sum(1 for s in subscriptions if s.is_active)]
        )
        writer.writerow(["Total Monthly Cost:", f"{total_monthly:.2f}"])
        writer.writerow(["Total Yearly Cost:", f"{total_monthly * 12:.2f}"])

        return output.getvalue()

    @staticmethod
    def generate_pdf_html(
        subscriptions: List[Subscription],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> str:
        """
        Generate HTML for PDF export (can be converted to PDF client-side or server-side).

        Args:
            subscriptions: List of subscription objects to export
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            HTML content as string
        """
        # Calculate statistics
        active_subs = [s for s in subscriptions if s.is_active]
        total_monthly = sum(
            ExportService._normalize_billing_to_monthly(
                float(s.amount) if s.amount else 0.0, s.billing_cycle
            )
            for s in active_subs
        )

        # Group by category
        by_category = {}
        for sub in active_subs:
            cat = sub.category or "other"
            if cat not in by_category:
                by_category[cat] = {"count": 0, "cost": 0.0}
            by_category[cat]["count"] += 1
            by_category[cat]["cost"] += ExportService._normalize_billing_to_monthly(
                float(sub.amount) if sub.amount else 0.0, sub.billing_cycle
            )

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Subscription Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            color: #333;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #3182ce;
            padding-bottom: 20px;
        }}
        .header h1 {{
            color: #3182ce;
            margin: 0;
        }}
        .metadata {{
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }}
        .summary {{
            background: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .summary h2 {{
            margin-top: 0;
            color: #3182ce;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }}
        .stat {{
            background: white;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #3182ce;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #2d3748;
            margin-top: 5px;
        }}
        .category-breakdown {{
            margin-bottom: 30px;
        }}
        .category-breakdown h3 {{
            color: #3182ce;
        }}
        .category-item {{
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid #e2e8f0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background: #3182ce;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        tr:hover {{
            background: #f7fafc;
        }}
        .status-active {{
            color: #38a169;
            font-weight: 600;
        }}
        .status-inactive {{
            color: #718096;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #666;
            font-size: 12px;
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Subscription Report</h1>
        <div class="metadata">
            <p>Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            {f'<p>Period: {start_date.strftime("%B %d, %Y")} - {end_date.strftime("%B %d, %Y")}</p>' if start_date and end_date else ''}
        </div>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <div class="stats-grid">
            <div class="stat">
                <div class="stat-label">Total Subscriptions</div>
                <div class="stat-value">{len(subscriptions)}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Active Subscriptions</div>
                <div class="stat-value">{len(active_subs)}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Monthly Cost</div>
                <div class="stat-value">${total_monthly:.2f}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Yearly Cost</div>
                <div class="stat-value">${total_monthly * 12:.2f}</div>
            </div>
        </div>
    </div>

    <div class="category-breakdown">
        <h3>Spending by Category</h3>
        {''.join(f'<div class="category-item"><span>{cat.title()}</span><span><strong>{data["count"]}</strong> subscriptions - <strong>${data["cost"]:.2f}/mo</strong></span></div>' for cat, data in sorted(by_category.items(), key=lambda x: x[1]['cost'], reverse=True))}
    </div>

    <h3>Subscription Details</h3>
    <table>
        <thead>
            <tr>
                <th>Provider</th>
                <th>Amount</th>
                <th>Billing</th>
                <th>Category</th>
                <th>Next Renewal</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
"""

        for sub in sorted(
            subscriptions, key=lambda s: (not s.is_active, s.provider.lower())
        ):
            status_class = "status-active" if sub.is_active else "status-inactive"
            status_text = "Active" if sub.is_active else "Inactive"
            amount_text = (
                f"{float(sub.amount):.2f} {sub.currency}" if sub.amount else "N/A"
            )
            renewal_text = (
                sub.next_renewal_date.strftime("%b %d, %Y")
                if sub.next_renewal_date
                else "N/A"
            )

            html += f"""
            <tr>
                <td><strong>{sub.provider}</strong>{f'<br><small style="color: #666;">{sub.custom_label}</small>' if sub.custom_label else ''}</td>
                <td>{amount_text}</td>
                <td>{sub.billing_cycle.title()}</td>
                <td>{sub.category.title()}</td>
                <td>{renewal_text}</td>
                <td class="{status_class}">{status_text}</td>
            </tr>
"""

        html += """
        </tbody>
    </table>

    <div class="footer">
        <p>Generated by Subscription Tracker</p>
    </div>
</body>
</html>
"""

        return html
