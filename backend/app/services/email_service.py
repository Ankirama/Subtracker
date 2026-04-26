"""Backward-compatibility shim.

The actual implementation lives in :mod:`app.services.email.transport`.
New code should import from there directly. This shim is kept for the
existing call sites and tests that import from
``app.services.email_service`` and will be removed in a follow-up
cleanup PR.

Note: the 3 typed wrappers ``send_renewal_reminder``,
``send_weekly_summary`` and ``send_monthly_summary`` (sole callers were
in ``notification_service.py``) were removed during the C1 Phase 5
consolidation. ``notification_service`` now calls
``EmailTemplates.generate_*`` + ``send_email`` directly. The 2FA and
verification typed wrappers are preserved on ``EmailService`` because
``api/_email_dispatch.py`` still uses them.
"""

from app.services.email.transport import EmailService  # noqa: F401

__all__ = ["EmailService"]
