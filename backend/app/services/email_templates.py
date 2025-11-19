"""
HTML email templates for subscription summaries.

Beautiful, responsive templates that work across email clients.
"""
from typing import Dict, Any


class EmailTemplates:
    """Email template generator for summaries."""

    @staticmethod
    def generate_summary_email(summary_data: Dict[str, Any]) -> str:
        """
        Generate HTML email for subscription summary.

        Args:
            summary_data: Summary data from SummaryService

        Returns:
            HTML string for email
        """
        period = summary_data['period_type'].title()
        user_name = summary_data['user_name']

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your {period} Subscription Summary</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 700;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px 20px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border: 1px solid #e9ecef;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: 700;
            color: #667eea;
            margin: 0;
        }}
        .stat-label {{
            font-size: 14px;
            color: #6c757d;
            margin: 5px 0 0 0;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 700;
            color: #2d3748;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
        }}
        .insight-box {{
            background: #f0f4ff;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
        }}
        .insight-box p {{
            margin: 5px 0;
            color: #4a5568;
        }}
        .subscription-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .subscription-item {{
            display: flex;
            justify-content: space-between;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 6px;
            margin-bottom: 8px;
        }}
        .subscription-name {{
            font-weight: 600;
            color: #2d3748;
        }}
        .subscription-cost {{
            color: #667eea;
            font-weight: 600;
        }}
        .category-item {{
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid #e9ecef;
        }}
        .category-item:last-child {{
            border-bottom: none;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-success {{
            background: #d4edda;
            color: #155724;
        }}
        .badge-danger {{
            background: #f8d7da;
            color: #721c24;
        }}
        .badge-info {{
            background: #d1ecf1;
            color: #0c5460;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 14px;
            color: #6c757d;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background: #667eea;
            color: white !important;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin-top: 20px;
        }}
        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: #6c757d;
        }}
        @media only screen and (max-width: 600px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {period} Subscription Summary</h1>
            <p>Hi {user_name}! Here's your subscription overview</p>
            <p style="font-size: 14px; opacity: 0.8;">{summary_data['start_date']} - {summary_data['end_date']}</p>
        </div>

        <div class="content">
            <!-- Key Stats -->
            <div class="stats-grid">
                <div class="stat-card">
                    <p class="stat-value">{summary_data['total_subscriptions']}</p>
                    <p class="stat-label">Active Subscriptions</p>
                </div>
                <div class="stat-card">
                    <p class="stat-value">€{summary_data['total_monthly_cost']}</p>
                    <p class="stat-label">Monthly Cost</p>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{summary_data['new_subscriptions_count']}</p>
                    <p class="stat-label">New This Period</p>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{summary_data['cancelled_subscriptions_count']}</p>
                    <p class="stat-label">Cancelled</p>
                </div>
            </div>

            <!-- Insights -->
            {EmailTemplates._render_insights(summary_data['insights'])}

            <!-- AI Optimization Insights -->
            {EmailTemplates._render_ai_insights(summary_data.get('ai_insights', []))}

            <!-- AI Recommendations -->
            {EmailTemplates._render_ai_recommendations(summary_data.get('ai_recommendations', []), summary_data.get('potential_savings', 0.0))}

            <!-- Changes This Period -->
            {EmailTemplates._render_changes(summary_data)}

            <!-- Top Categories -->
            {EmailTemplates._render_top_categories(summary_data['top_categories'])}

            <!-- Top Subscriptions -->
            {EmailTemplates._render_top_subscriptions(summary_data['top_subscriptions'])}

            <!-- Upcoming Renewals -->
            {EmailTemplates._render_upcoming_renewals(summary_data['upcoming_renewals'])}

            <!-- Call to Action -->
            <div style="text-align: center; margin-top: 30px;">
                <a href="http://localhost:5173/subscriptions" class="button">
                    View All Subscriptions →
                </a>
            </div>
        </div>

        <div class="footer">
            <p>📧 SubTracker - Your Subscription Management Assistant</p>
            <p style="font-size: 12px; margin-top: 10px;">
                <a href="http://localhost:5173/notifications/settings" style="color: #667eea; text-decoration: none;">
                    Manage Email Preferences
                </a>
            </p>
        </div>
    </div>
</body>
</html>
"""
        return html

    @staticmethod
    def _render_insights(insights: list) -> str:
        """Render insights section."""
        if not insights:
            return ""

        html = '<div class="section"><div class="section-title">💡 Key Insights</div>'
        for insight in insights:
            html += f'<div class="insight-box"><p>{insight}</p></div>'
        html += '</div>'
        return html

    @staticmethod
    def _render_changes(summary_data: Dict[str, Any]) -> str:
        """Render new and cancelled subscriptions."""
        new_subs = summary_data['new_subscriptions']
        cancelled_subs = summary_data['cancelled_subscriptions']

        if not new_subs and not cancelled_subs:
            return ""

        html = '<div class="section"><div class="section-title">📋 Changes This Period</div>'

        if new_subs:
            html += '<p style="font-weight: 600; color: #2d3748; margin-bottom: 10px;">✅ New Subscriptions</p>'
            html += '<ul class="subscription-list">'
            for sub in new_subs:
                html += f'''
                    <li class="subscription-item">
                        <span class="subscription-name">{sub['provider']}</span>
                        <span class="subscription-cost">€{sub['amount']}/{sub['billing_cycle']}</span>
                    </li>
                '''
            html += '</ul>'

        if cancelled_subs:
            html += '<p style="font-weight: 600; color: #2d3748; margin: 20px 0 10px 0;">❌ Cancelled Subscriptions</p>'
            html += '<ul class="subscription-list">'
            for sub in cancelled_subs:
                html += f'''
                    <li class="subscription-item">
                        <span class="subscription-name">{sub['provider']}</span>
                        <span class="subscription-cost">€{sub['amount']}/{sub['billing_cycle']}</span>
                    </li>
                '''
            html += '</ul>'

        if summary_data['net_change'] != 0:
            change_type = "increased" if summary_data['net_change'] > 0 else "decreased"
            change_color = "#dc3545" if summary_data['net_change'] > 0 else "#28a745"
            html += f'''
                <p style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                    Your monthly spending {change_type} by
                    <span style="font-weight: 700; color: {change_color};">
                        €{abs(summary_data['net_change']):.2f}
                    </span>
                </p>
            '''

        html += '</div>'
        return html

    @staticmethod
    def _render_top_categories(top_categories: list) -> str:
        """Render top spending categories."""
        if not top_categories:
            return ""

        html = '<div class="section"><div class="section-title">📊 Top Spending Categories</div>'
        for cat in top_categories:
            category_name = cat['category'].replace('_', ' ').title()
            html += f'''
                <div class="category-item">
                    <div>
                        <span style="font-weight: 600; color: #2d3748;">{category_name}</span>
                        <span style="margin-left: 10px; color: #6c757d; font-size: 14px;">
                            ({cat['count']} subscription{'s' if cat['count'] != 1 else ''})
                        </span>
                    </div>
                    <span style="font-weight: 600; color: #667eea;">€{cat['cost']:.2f}/mo</span>
                </div>
            '''
        html += '</div>'
        return html

    @staticmethod
    def _render_top_subscriptions(top_subscriptions: list) -> str:
        """Render most expensive subscriptions."""
        if not top_subscriptions:
            return ""

        html = '<div class="section"><div class="section-title">💰 Most Expensive Subscriptions</div>'
        html += '<ul class="subscription-list">'
        for sub in top_subscriptions:
            html += f'''
                <li class="subscription-item">
                    <span class="subscription-name">{sub['provider']}</span>
                    <span class="subscription-cost">€{sub['monthly_cost']:.2f}/mo</span>
                </li>
            '''
        html += '</ul></div>'
        return html

    @staticmethod
    def _render_ai_insights(ai_insights: list) -> str:
        """Render AI-powered optimization insights section."""
        if not ai_insights:
            return ""

        html = '<div class="section"><div class="section-title">🤖 AI Optimization Insights</div>'
        for insight in ai_insights:
            html += f'<div class="insight-box" style="background: #fff4e6; border-left-color: #ff9800;"><p>{insight}</p></div>'
        html += '</div>'
        return html

    @staticmethod
    def _render_ai_recommendations(recommendations: list, potential_savings: float) -> str:
        """Render AI-powered recommendations section."""
        if not recommendations:
            return ""

        # Priority badge colors
        priority_colors = {
            'high': '#dc3545',
            'medium': '#ff9800',
            'low': '#28a745'
        }

        html = '<div class="section">'
        html += '<div class="section-title">💡 AI-Powered Recommendations</div>'

        if potential_savings > 0:
            html += f'''
                <p style="margin-bottom: 15px; padding: 12px; background: #e8f5e9; border-left: 4px solid #28a745; border-radius: 4px;">
                    <strong>💰 Potential Savings:</strong> €{potential_savings:.2f}/month (€{potential_savings * 12:.2f}/year)
                </p>
            '''

        html += '<ul class="subscription-list">'
        for rec in recommendations[:5]:  # Show top 5 recommendations
            priority = rec.get('priority', 'medium')
            priority_color = priority_colors.get(priority, '#ff9800')

            # Icon based on recommendation type
            icons = {
                'duplicate_consolidation': '🔄',
                'duplicate_review': '📋',
                'unused_subscription': '⏸️',
                'family_plan_upgrade': '👨‍👩‍👧‍👦',
                'annual_billing_savings': '📅',
                'alternative_provider': '🔄',
                'cost_reduction': '💰'
            }
            icon = icons.get(rec.get('type', ''), '💡')

            savings_text = ''
            if rec.get('potential_savings', 0) > 0:
                savings_text = f' <span style="color: #28a745; font-weight: 700;">Save €{rec["potential_savings"]:.2f}/mo</span>'

            html += f'''
                <li class="subscription-item">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <span style="font-size: 18px;">{icon}</span>
                            <span class="subscription-name">{rec.get('title', '')}</span>
                            <span class="badge" style="background: {priority_color}; color: white; font-size: 10px;">
                                {priority.upper()}
                            </span>
                        </div>
                        <p style="font-size: 14px; color: #6c757d; margin: 0;">
                            {rec.get('description', '')}{savings_text}
                        </p>
                    </div>
                </li>
            '''

        html += '</ul>'

        if len(recommendations) > 5:
            html += f'''
                <p style="text-align: center; margin-top: 15px; color: #6c757d; font-size: 14px;">
                    + {len(recommendations) - 5} more recommendations in your dashboard
                </p>
            '''

        html += '</div>'
        return html

    @staticmethod
    def _render_upcoming_renewals(upcoming_renewals: list) -> str:
        """Render upcoming renewal dates."""
        if not upcoming_renewals:
            return ""

        html = '<div class="section"><div class="section-title">🔔 Upcoming Renewals (Next 30 Days)</div>'
        html += '<ul class="subscription-list">'
        for renewal in upcoming_renewals:
            from datetime import datetime
            renewal_date = datetime.fromisoformat(renewal['renewal_date']).strftime('%b %d, %Y')
            html += f'''
                <li class="subscription-item">
                    <div>
                        <span class="subscription-name">{renewal['provider']}</span>
                        <div style="font-size: 12px; color: #6c757d; margin-top: 4px;">{renewal_date}</div>
                    </div>
                    <span class="subscription-cost">€{renewal['amount']}</span>
                </li>
            '''
        html += '</ul></div>'
        return html

    @staticmethod
    def generate_2fa_otp_email(user_name: str, otp_code: str, expires_in_minutes: int = 10) -> str:
        """
        Generate HTML email for 2FA OTP code.

        Args:
            user_name: User's name
            otp_code: 6-digit OTP code
            expires_in_minutes: Code expiration time in minutes

        Returns:
            HTML string for email
        """
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Two-Factor Authentication Code</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 700;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px 20px;
        }}
        .greeting {{
            font-size: 18px;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 20px;
        }}
        .otp-container {{
            background: #f8f9fa;
            border: 2px solid #667eea;
            border-radius: 8px;
            padding: 30px;
            text-align: center;
            margin: 30px 0;
        }}
        .otp-label {{
            font-size: 14px;
            color: #6c757d;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .otp-code {{
            font-size: 42px;
            font-weight: 700;
            color: #667eea;
            letter-spacing: 8px;
            margin: 10px 0;
            font-family: 'Courier New', Courier, monospace;
        }}
        .otp-expiry {{
            font-size: 14px;
            color: #dc3545;
            margin-top: 10px;
            font-weight: 600;
        }}
        .info-box {{
            background: #fff4e6;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box p {{
            margin: 5px 0;
            color: #4a5568;
            font-size: 14px;
        }}
        .security-notice {{
            background: #f0f4ff;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .security-notice p {{
            margin: 5px 0;
            color: #4a5568;
            font-size: 14px;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 14px;
            color: #6c757d;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        @media only screen and (max-width: 600px) {{
            .otp-code {{
                font-size: 32px;
                letter-spacing: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Two-Factor Authentication</h1>
            <p>Your security verification code</p>
        </div>

        <div class="content">
            <div class="greeting">Hi {user_name}!</div>

            <p>You're receiving this email because someone attempted to log in to your Subscription Tracker account.</p>

            <p>Enter the following verification code to complete your login:</p>

            <div class="otp-container">
                <div class="otp-label">Verification Code</div>
                <div class="otp-code">{otp_code}</div>
                <div class="otp-expiry">⏱️ Expires in {expires_in_minutes} minutes</div>
            </div>

            <div class="info-box">
                <p><strong>💡 Quick Tips:</strong></p>
                <p>• This code is single-use only</p>
                <p>• Enter it in your login screen to proceed</p>
                <p>• The code is case-sensitive</p>
            </div>

            <div class="security-notice">
                <p><strong>🛡️ Security Notice:</strong></p>
                <p>If you didn't attempt to log in, please ignore this email and consider changing your password immediately.</p>
                <p>Never share this code with anyone. Our team will never ask for your verification code.</p>
            </div>
        </div>

        <div class="footer">
            <p>📧 SubTracker - Your Subscription Management Assistant</p>
            <p style="font-size: 12px; margin-top: 10px; color: #999;">
                This is an automated security email. Please do not reply.
            </p>
        </div>
    </div>
</body>
</html>
"""
        return html

    @staticmethod
    def generate_email_verification_email(user_name: str, verification_url: str) -> str:
        """
        Generate HTML email for email verification.

        Args:
            user_name: User's display name or email
            verification_url: Complete URL for email verification

        Returns:
            HTML string for email
        """
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Complete Your Registration</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 700;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px 20px;
        }}
        .greeting {{
            font-size: 18px;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 20px;
        }}
        .welcome-message {{
            background: #f0f4ff;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .welcome-message p {{
            margin: 5px 0;
            color: #4a5568;
            font-size: 16px;
        }}
        .button-container {{
            text-align: center;
            margin: 40px 0;
        }}
        .verify-button {{
            display: inline-block;
            padding: 16px 40px;
            background: #667eea;
            color: white !important;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 700;
            font-size: 16px;
            transition: background 0.3s ease;
        }}
        .verify-button:hover {{
            background: #5568d3;
        }}
        .info-box {{
            background: #fff4e6;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-box p {{
            margin: 5px 0;
            color: #4a5568;
            font-size: 14px;
        }}
        .alt-link {{
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
            word-break: break-all;
        }}
        .alt-link p {{
            margin: 5px 0;
            font-size: 14px;
            color: #6c757d;
        }}
        .alt-link a {{
            color: #667eea;
            text-decoration: none;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 14px;
            color: #6c757d;
        }}
        .footer p {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✨ Welcome to SubTracker!</h1>
            <p>Let's complete your registration</p>
        </div>

        <div class="content">
            <div class="greeting">Hi {user_name}!</div>

            <div class="welcome-message">
                <p><strong>🎉 Thank you for signing up!</strong></p>
                <p>We're excited to help you manage your subscriptions and take control of your recurring expenses.</p>
            </div>

            <p>To get started, please verify your email address by clicking the button below:</p>

            <div class="button-container">
                <a href="{verification_url}" class="verify-button">
                    Complete your Registration
                </a>
            </div>

            <div class="info-box">
                <p><strong>⏱️ Important:</strong></p>
                <p>• This verification link expires in 24 hours</p>
                <p>• The link can only be used once</p>
                <p>• You won't be able to log in until you verify your email</p>
            </div>

            <div class="alt-link">
                <p><strong>Can't click the button?</strong></p>
                <p>Copy and paste this link into your browser:</p>
                <p><a href="{verification_url}">{verification_url}</a></p>
            </div>

            <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">
                If you didn't create an account, you can safely ignore this email.
            </p>
        </div>

        <div class="footer">
            <p>📧 SubTracker - Your Subscription Management Assistant</p>
            <p style="font-size: 12px; margin-top: 10px; color: #999;">
                This is an automated email. Please do not reply.
            </p>
        </div>
    </div>
</body>
</html>
"""
        return html
