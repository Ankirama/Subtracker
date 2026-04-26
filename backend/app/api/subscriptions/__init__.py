"""API endpoints for subscription management.

Split into sub-modules per concern. The aggregate router is exported from
``router.py``; this ``__init__`` re-exports it so existing imports
(``from app.api.subscriptions import router``) keep working.
"""

from app.api.subscriptions.router import router  # noqa: F401
