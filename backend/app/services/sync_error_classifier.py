"""Pure classifier mapping exception → (error_type, severity).

Used by services/sync_error_recorder.py and the per-email try/except in
tasks/email_sync/stages/classification.py.

No DB access, no I/O — kept dependency-free for fast unit tests.
"""

from typing import Tuple

from sqlalchemy import exc as sa_exc

from app.services.subscription_extractor import ExtractionError


def classify_exception(exc: Exception) -> Tuple[str, str]:
    """Classify an exception raised during single-email processing.

    Returns:
        Tuple ``(error_type, severity)``.
        ``error_type`` is one of: ``schema_too_long``, ``encoding_error``,
        ``db_constraint``, ``extraction_failed``, ``unexpected``.
        ``severity`` is one of: ``low``, ``medium``, ``high``.
    """
    if isinstance(exc, sa_exc.DataError):
        if "value too long" in str(exc).lower():
            return "schema_too_long", "medium"
        return "db_constraint", "medium"

    if isinstance(exc, UnicodeError):
        return "encoding_error", "medium"

    if isinstance(exc, sa_exc.IntegrityError):
        return "db_constraint", "medium"

    if isinstance(exc, ExtractionError):
        return "extraction_failed", "low"

    return "unexpected", "high"
