"""Backward-compatibility shim.

The actual implementation lives in :mod:`app.services.email.templates`.
New code should import from there directly. This shim is kept for the
existing call sites and tests that import from
``app.services.email_templates`` and will be removed in a follow-up
cleanup PR.
"""

from app.services.email.templates import EmailTemplates  # noqa: F401

__all__ = ["EmailTemplates"]
