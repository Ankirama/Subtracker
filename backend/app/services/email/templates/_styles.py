"""Shared style constants for email templates.

Reserved for future CSS factoring. The 6 email templates currently embed
their own CSS in ``<style>`` blocks for byte-identical output preservation
during the Phase 5 ``services/email/`` migration. A follow-up cleanup PR
can factor out the duplicated header/footer/container CSS into a
``BASE_STYLES`` constant and a ``render_layout`` helper here without
changing rendered output (verified via snapshot fingerprints).
"""

# Common gradient used across summary, OTP, verification emails.
HEADER_GRADIENT = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"

# Common monthly-summary gradient
MONTHLY_GRADIENT = "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"

# Logo color for renewal_reminder/weekly_summary/monthly_summary inline templates
INLINE_LOGO_COLOR = "#3182ce"
