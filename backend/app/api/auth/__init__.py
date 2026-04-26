"""API endpoints for authentication.

Split into sub-modules per flow (registration, login, two-factor,
account). The aggregate router is exported from ``router.py``; this
``__init__`` re-exports it so existing imports
(``from app.api import auth``; ``auth.router``) keep working.
"""

from app.api.auth.router import router  # noqa: F401
