"""Pipeline stages for the email-sync orchestrator.

Three stages mirror the comments that already existed in the original
1306-line ``email_sync.py`` (``# STAGE 1`` line 207, ``# STAGE 2`` line
277, ``# STAGE 3`` line 330):

  - ``classification``: fetch + Message-ID dedup + system-email filter +
    batch classification + ``EmailMessage`` row creation.
  - ``extraction``: extraction-needs decision + batch extraction.
  - ``persistence``: dedup, subscription upsert, association-table writes,
    delegating to ``price_history``, ``renewal_step``, ``cancellation_step``.
"""
