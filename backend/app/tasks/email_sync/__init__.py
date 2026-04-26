"""Email-sync sub-package (C1 Phase 8b).

The 1306-line ``backend/app/tasks/email_sync.py`` module was split into
this sub-package along the pipeline-stage axis advertised in the
original file's own ``# STAGE 1`` / ``# STAGE 2`` / ``# STAGE 3``
comments.

Layout:

  - ``celery_tasks``    Celery task definitions (``DatabaseTask``,
                        ``sync_mailbox_emails``, ``check_scheduled_syncs``).
  - ``orchestrator``    ``_sync_mailbox_async``: provider bootstrap,
                        date-filter resolution, batch loop.
  - ``stages/``
      ``classification`` Stage 1 — fetch + Message-ID dedup + system-email
                         filter + classification + EmailMessage rows.
      ``extraction``     Stage 2 — extraction-needs decision + extractor.
      ``persistence``    Stage 3 — dedup + upsert + association write,
                         delegating to ``price_history``, ``renewal_step``,
                         ``cancellation_step``.
  - ``filters``         ``parse_date_filter``, ``filter_subscription_data``,
                        ``VALID_SUBSCRIPTION_FIELDS``.
  - ``progress_tracker`` Per-batch mailbox progress fields + cancellation
                        finalisation of ``SyncHistory``.
  - ``price_history``    Thin facade over
                        ``app.services.price_history_recorder``.
  - ``renewal_step``     Wraps ``RenewalCalculator`` + reactivation detection.
  - ``cancellation_step`` Cancellation-suggestion creation policy.
  - ``status_reconciler`` ``update_subscription_statuses`` (post-sync hook
                          AND the public endpoint's implementation).

Public API (re-exported here for back-compat with existing callers):

  - ``sync_mailbox_emails``       — Celery task imported by ``api/mailboxes``
                                    and ``claudedocs/resync_guide.md``.
  - ``check_scheduled_syncs``     — Celery Beat entry-point.
  - ``update_subscription_statuses`` — used by
                                    ``api/subscriptions/status_reconcile``.
  - ``_sync_mailbox_async``       — used by ``test_email_pipeline_seam``.
  - ``parse_date_filter``         — used by ``test_email_sync``.
  - ``filter_subscription_data``  — used by tests.
  - ``DatabaseTask``              — Celery base class.
"""

from .celery_tasks import (
    DatabaseTask,
    check_scheduled_syncs,
    sync_mailbox_emails,
)
from .filters import filter_subscription_data, parse_date_filter
from .orchestrator import _sync_mailbox_async
from .status_reconciler import update_subscription_statuses

__all__ = [
    "DatabaseTask",
    "_sync_mailbox_async",
    "check_scheduled_syncs",
    "filter_subscription_data",
    "parse_date_filter",
    "sync_mailbox_emails",
    "update_subscription_statuses",
]
