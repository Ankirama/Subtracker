"""Price-history bookkeeping for the email-sync pipeline.

Thin facade re-exporting the helpers from
``app.services.price_history_recorder`` for use inside the
``stages.persistence`` module. The recorder service owns the actual
``PriceHistory`` row creation arithmetic; this module's role is to be
the canonical "where does email-sync record price changes" location so
the call sites in ``stages.persistence`` only need to import from here.

The three historical inline paths (audit §A.4):

  Path 1 — AI-flagged price update (extraction returns ``is_price_update=True``)
      → ``record_price_change``
  Path 2 — Post-hoc amount diff on existing subscription
      → ``record_price_change``
  Path 3 — Initial price for newly created subscription
      → ``record_initial_price``

Both helpers add the new ORM instance to ``db`` but do NOT commit — the
caller (``stages.persistence``) controls transaction boundaries to
preserve the per-email commit semantics that the Phase 1 chartests
verify.
"""

from app.services.price_history_recorder import (
    record_initial_price,
    record_price_change,
)

__all__ = ["record_price_change", "record_initial_price"]
