"""Aggregate APIRouter for /subscriptions endpoints.

Includes one sub-router per concern. Each sub-module declares its own
``router = APIRouter()`` (no prefix) and registers handlers; this module
mounts them all under a single parent router. The ``/api/subscriptions``
prefix is applied by ``app.main`` when including this aggregate router.
"""

from fastapi import APIRouter

from app.api.subscriptions import (
    analytics,
    cancellation_suggestion,
    crud,
    duplicates,
    feedback,
    merge_split,
    price_history,
    stats,
    status_reconcile,
)

router = APIRouter()

# Note: order matters — static paths (e.g. /stats, /duplicates) must be
# registered before catch-all path-param routes (/{subscription_id}) so that
# FastAPI matches them first.
router.include_router(stats.router)
router.include_router(analytics.router)
router.include_router(duplicates.router)
router.include_router(status_reconcile.router)
router.include_router(feedback.router)
router.include_router(merge_split.router)
router.include_router(price_history.router)
router.include_router(cancellation_suggestion.router)
router.include_router(crud.router)
