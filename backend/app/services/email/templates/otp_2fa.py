"""Two-factor authentication OTP email template.

Migrated unchanged from ``services/email_templates.py`` so HTML output is
byte-identical (verified via existing ``test_email_templates.py`` tests).
"""

from __future__ import annotations


def generate_2fa_otp_email(
    user_name: str, otp_code: str, expires_in_minutes: int = 10
) -> str:
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
