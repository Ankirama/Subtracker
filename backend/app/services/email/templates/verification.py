"""Email verification template (sent after sign-up).

Migrated unchanged from ``services/email_templates.py`` so HTML output is
byte-identical (verified via existing ``test_email_templates.py`` tests).
"""

from __future__ import annotations


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
