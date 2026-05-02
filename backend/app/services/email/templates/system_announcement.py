"""System announcement email template.

Migrated verbatim from ``tasks/system_announcements.py::send_announcement_email``.
HTML and plain-text bodies are byte-identical to the previous inline strings.
"""

from __future__ import annotations

import markdown


_PRIORITY_STYLES: dict[str, dict[str, str]] = {
    "high": {
        "color": "#e53e3e",
        "bg": "#fed7d7",
        "border": "#fc8181",
        "badge": "🔴 HIGH PRIORITY",
    },
    "low": {
        "color": "#3182ce",
        "bg": "#bee3f8",
        "border": "#90cdf4",
        "badge": "🔵 INFORMATION",
    },
    "medium": {
        "color": "#d69e2e",
        "bg": "#fef5e7",
        "border": "#f6e05e",
        "badge": "🟡 ANNOUNCEMENT",
    },
}


def generate_system_announcement_email(
    notification_title: str,
    notification_message: str,
    priority: str,
) -> tuple[str, str]:
    """Build the (html_content, plain_content) pair for a system announcement.

    Args:
        notification_title: ``Notification.title`` (may include the "📢 " emoji prefix).
        notification_message: ``Notification.message`` (Markdown source).
        priority: One of "low", "medium", "high".

    Returns:
        Tuple of (html_content, plain_content).
    """
    style = _PRIORITY_STYLES.get(priority, _PRIORITY_STYLES["medium"])
    banner_color = style["color"]
    banner_bg = style["bg"]
    banner_border = style["border"]
    priority_badge = style["badge"]

    # Strip the emoji prefix so the body heading reads cleanly.
    title = notification_title.replace("📢 ", "")

    md = markdown.Markdown(extensions=["extra", "nl2br", "sane_lists"])
    message_html = md.convert(notification_message)

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Priority Banner -->
        <div style="background-color: {banner_bg}; border: 2px solid {banner_border}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 24px; color: {banner_color};">
                📢 SYSTEM ANNOUNCEMENT
            </h1>
            <p style="margin: 10px 0 0 0; font-size: 14px; color: {banner_color}; font-weight: bold;">
                {priority_badge}
            </p>
        </div>

        <!-- Announcement Content -->
        <div style="background-color: #fff; border: 2px solid {banner_color}; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">{title}</h2>
            <div style="font-size: 16px; color: #34495e; line-height: 1.6;">
                {message_html}
            </div>
        </div>

        <!-- Action Button -->
        <div style="text-align: center; margin: 30px 0;">
            <a href="http://localhost:5173/notifications"
               style="background-color: {banner_color}; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 16px;">
                View All Notifications
            </a>
        </div>

        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
            <p style="margin: 0; color: #666; font-size: 14px;">
                📬 Stay informed about important updates and announcements<br>
                Manage your notification preferences in settings
            </p>
        </div>

        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #95a5a6; font-size: 12px;">
            <p>
                You're receiving this system announcement as a Subscription Tracker user.<br>
                <a href="http://localhost:5173/notifications/settings" style="color: #3498db;">Manage notification settings</a>
            </p>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
📢 SYSTEM ANNOUNCEMENT
{priority_badge}

{title}

{notification_message}

View all notifications: http://localhost:5173/notifications
Manage settings: http://localhost:5173/notifications/settings

---
Subscription Tracker - System Announcements
    """

    return html_content, plain_content
