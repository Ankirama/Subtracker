"""Circuit breaker for the email-sync pipeline.

Raised by stages/classification.py when too many consecutive ``unexpected``
errors occur. Aborts the sync gracefully — the wrapping Celery task
catches it and transitions the mailbox to ``last_sync_status='failed'``
without retry (see celery_tasks.py).
"""


class SyncCircuitBreakerError(Exception):
    """Aborts an email sync after too many consecutive unexpected errors."""

    def __init__(self, threshold: int, error_count: int):
        self.threshold = threshold
        self.error_count = error_count
        super().__init__(
            f"Sync circuit breaker tripped: {error_count} consecutive unexpected "
            f"errors (threshold: {threshold})"
        )


CIRCUIT_BREAKER_THRESHOLD = 5
