"""
Email service for sending notifications via Resend.

Handles all email delivery with HTML templates for different notification types.
"""

import resend
from typing import Optional, List
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.config import settings
from app.models.notification import NotificationType
from app.utils.config_helper import get_config_value
from app.services.email_templates import EmailTemplates

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Resend."""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize Resend client.

        Args:
            db: Optional database session to check admin settings
        """
        # Get config values (admin settings override env vars)
        api_key = get_config_value("resend.api_key", settings.RESEND_API_KEY, db)
        from_email = get_config_value(
            "resend.from_email", settings.RESEND_FROM_EMAIL, db
        )
        from_name = get_config_value("resend.from_name", settings.RESEND_FROM_NAME, db)

        # Configure Resend with API key
        resend.api_key = api_key

        # Store from email info
        self.from_email = from_email
        self.from_name = from_name

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Send an email via Resend.

        Returns (success: bool, error_message: Optional[str])
        """
        try:
            # Prepare email params
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            # Add plain text if provided
            if plain_content:
                params["text"] = plain_content

            # Send email via Resend
            email_response = resend.Emails.send(params)

            # Check if email was sent successfully
            if email_response and email_response.get("id"):
                logger.info(
                    f"Email sent successfully to {to_email}: {subject} (ID: {email_response['id']})"
                )
                return True, None
            else:
                error_msg = "Resend returned no email ID"
                logger.error(f"Failed to send email to {to_email}: {error_msg}")
                return False, error_msg

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Exception sending email to {to_email}: {error_msg}")
            return False, error_msg

    def send_renewal_reminder(
        self,
        to_email: str,
        user_name: str,
        subscription_name: str,
        renewal_date: datetime,
        amount: float,
        currency: str,
        days_until_renewal: int,
    ) -> tuple[bool, Optional[str]]:
        """Send renewal reminder email."""
        subject = f"Reminder: {subscription_name} renews in {days_until_renewal} days"

        html_content = self._get_renewal_reminder_template(
            user_name=user_name,
            subscription_name=subscription_name,
            renewal_date=renewal_date,
            amount=amount,
            currency=currency,
            days_until_renewal=days_until_renewal,
        )

        plain_content = f"""
Hi {user_name},

This is a reminder that your {subscription_name} subscription will renew in {days_until_renewal} days.

Renewal Date: {renewal_date.strftime('%B %d, %Y')}
Amount: {currency} {amount:.2f}

If you wish to cancel or modify this subscription, please log in to your Subscription Tracker account.

Best regards,
Subscription Tracker Team
        """.strip()

        return self.send_email(to_email, subject, html_content, plain_content)

    def send_weekly_summary(
        self,
        to_email: str,
        user_name: str,
        total_spent: float,
        currency: str,
        subscriptions: List[dict],
        upcoming_renewals: List[dict],
    ) -> tuple[bool, Optional[str]]:
        """Send weekly spending summary email."""
        subject = f"Your Weekly Subscription Summary - {currency} {total_spent:.2f}"

        html_content = self._get_weekly_summary_template(
            user_name=user_name,
            total_spent=total_spent,
            currency=currency,
            subscriptions=subscriptions,
            upcoming_renewals=upcoming_renewals,
        )

        plain_content = f"""
Hi {user_name},

Here's your weekly subscription summary.

Total Spent This Week: {currency} {total_spent:.2f}

Active Subscriptions: {len(subscriptions)}

Upcoming Renewals: {len(upcoming_renewals)}

Log in to your Subscription Tracker account to view more details.

Best regards,
Subscription Tracker Team
        """.strip()

        return self.send_email(to_email, subject, html_content, plain_content)

    def send_monthly_summary(
        self,
        to_email: str,
        user_name: str,
        total_spent: float,
        currency: str,
        subscriptions: List[dict],
        spending_breakdown: dict,
        comparison_last_month: Optional[dict] = None,
    ) -> tuple[bool, Optional[str]]:
        """Send monthly spending summary email."""
        subject = f"Your Monthly Subscription Summary - {currency} {total_spent:.2f}"

        html_content = self._get_monthly_summary_template(
            user_name=user_name,
            total_spent=total_spent,
            currency=currency,
            subscriptions=subscriptions,
            spending_breakdown=spending_breakdown,
            comparison_last_month=comparison_last_month,
        )

        plain_content = f"""
Hi {user_name},

Here's your monthly subscription summary.

Total Spent This Month: {currency} {total_spent:.2f}

Active Subscriptions: {len(subscriptions)}

Log in to your Subscription Tracker account to view detailed analytics.

Best regards,
Subscription Tracker Team
        """.strip()

        return self.send_email(to_email, subject, html_content, plain_content)

    def send_2fa_otp_email(
        self, to_email: str, user_name: str, otp_code: str, expires_in_minutes: int = 10
    ) -> tuple[bool, Optional[str]]:
        """
        Send 2FA OTP code email.

        Args:
            to_email: Recipient email address
            user_name: User's name
            otp_code: 6-digit OTP code
            expires_in_minutes: Code expiration time in minutes

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        subject = f"Your Two-Factor Authentication Code - {otp_code}"

        html_content = EmailTemplates.generate_2fa_otp_email(
            user_name=user_name,
            otp_code=otp_code,
            expires_in_minutes=expires_in_minutes,
        )

        plain_content = f"""
Hi {user_name},

You're receiving this email because someone attempted to log in to your Subscription Tracker account.

Your verification code is: {otp_code}

This code will expire in {expires_in_minutes} minutes.

SECURITY NOTICE:
If you didn't attempt to log in, please ignore this email and consider changing your password immediately.
Never share this code with anyone.

Subscription Tracker Team
        """.strip()

        return self.send_email(to_email, subject, html_content, plain_content)

    def send_email_verification(
        self, to_email: str, user_name: str, verification_url: str
    ) -> tuple[bool, Optional[str]]:
        """
        Send email verification email.

        Args:
            to_email: Recipient email address
            user_name: User's display name or email
            verification_url: Complete URL for email verification

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        subject = "Complete Your Registration - Subscription Tracker"

        html_content = EmailTemplates.generate_email_verification_email(
            user_name=user_name, verification_url=verification_url
        )

        plain_content = f"""
Hi {user_name}!

Thank you for signing up for Subscription Tracker!

To complete your registration and start managing your subscriptions, please verify your email address by clicking the link below:

{verification_url}

Important:
• This verification link expires in 24 hours
• The link can only be used once
• You won't be able to log in until you verify your email

If you didn't create an account, you can safely ignore this email.

Best regards,
Subscription Tracker Team
        """.strip()

        return self.send_email(to_email, subject, html_content, plain_content)

    def _get_renewal_reminder_template(
        self,
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

    def _get_weekly_summary_template(
        self,
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

    def _get_monthly_summary_template(
        self,
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
        for sub in sorted(
            subscriptions, key=lambda x: x.get("amount", 0), reverse=True
        )[:10]:
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


# Singleton instance
email_service = EmailService()
