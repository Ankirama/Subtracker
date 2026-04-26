"""Aggregate APIRouter for ``/api/auth`` endpoints.

Includes one sub-router per concern. Each sub-module declares its own
``router = APIRouter()`` (no prefix) and registers handlers; this
module mounts them all under a single parent router. The
``/api/auth`` prefix is applied by ``app.main`` when including this
aggregate router.

Module composition (per audit Phase 7):

  - ``registration``   POST /register, /verify-email, /resend-verification
  - ``login``          POST /login, /refresh, /logout, GET /me
  - ``two_factor``     6 routes under /2fa/*
  - ``account``        PUT /me/profile, /me/password, /me/preferences,
                       GET/PATCH /me/language, DELETE /me
"""

from fastapi import APIRouter

from app.api.auth import account, login, registration, two_factor

router = APIRouter()

# Note: order matters when multiple sub-routers register paths whose
# prefixes overlap. The `/me/*` static paths in `account` and `login`
# do not conflict (different verbs / fully-distinct subpaths) but we
# still place the more-specific 2FA routes (/2fa/...) before the
# generic /me ones so FastAPI's path-matching is predictable in the
# OpenAPI schema.
router.include_router(registration.router)
router.include_router(login.router)
router.include_router(two_factor.router)
router.include_router(account.router)
