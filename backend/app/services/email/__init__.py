"""Email package: rendering (templates) + delivery (transport).

C1 Phase 5 consolidation of the previously-split
``services/email_templates.py`` (rendering) and
``services/email_service.py`` (delivery).

Sub-packages:
    templates: HTML email template generators.
    transport: Resend wrapper (``EmailService``).

Recommended imports:
    from app.services.email.templates import EmailTemplates
    from app.services.email.transport import EmailService
"""

from __future__ import annotations

from app.services.email.templates import EmailTemplates

__all__ = ["EmailTemplates"]
