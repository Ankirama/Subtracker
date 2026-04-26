"""Structural protocols for the email-sync pipeline's AI collaborators.

This module defines the interface seam used by `app.tasks.email_sync` to
inject the three AI services it depends on (classification, extraction,
service-reference matching) without taking a hard module-level dependency on
their concrete implementations. The seam neutralises the historical
`api -> tasks -> services` import-DAG triangle (audit finding A.1) by
letting `tasks/email_sync.py` import these symbols at module load time
without inviting circulars: the Protocols here depend on nothing from the
`api` or `tasks` layers, and the concrete implementations consume only
shared models. The seam is also the foundation for testability: callers
(tests in particular) can inject mocks compatible with these structural
types instead of monkeypatching module attributes.
"""

from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage


class AIClassifier(Protocol):
    """Callable that classifies a batch of emails as subscription-related or not.

    Mirrors the signature of
    `app.services.ai_classifier.classify_emails_batch`. Implementations are
    expected to preserve the input order of `emails` in the returned list.
    """

    def __call__(
        self,
        emails: List[EmailMessage],
        db: Optional[Session] = None,
        initial_batch_size: int = 10,
        min_batch_size: int = 2,
    ) -> Awaitable[List[Dict[str, Any]]]: ...


class SubscriptionExtractor(Protocol):
    """Callable that extracts subscription data from a batch of emails.

    Mirrors the signature of
    `app.services.subscription_extractor.extract_subscriptions_batch`.
    Each element in the returned list is either an extraction dict or
    ``None`` when no subscription could be extracted, preserving the input
    order of `emails`.
    """

    def __call__(
        self,
        emails: List[EmailMessage],
        db: Optional[Session] = None,
        initial_batch_size: int = 10,
        min_batch_size: int = 2,
    ) -> Awaitable[List[Optional[Dict[str, Any]]]]: ...


class ReferenceExtractorProtocol(Protocol):
    """Surface of `ReferenceExtractor` consumed by the dedup strategy.

    The email-sync pipeline only needs `can_match_subscription` to drive
    `app.services.dedup_strategy.find_best_match`; the full
    `ReferenceExtractor` class exposes additional methods (`extract`,
    `find_matching_subscription`) that are not part of this seam. Keep this
    Protocol minimal so test doubles do not have to implement methods the
    pipeline never calls.
    """

    def can_match_subscription(
        self,
        references: Dict[str, str],
        existing_metadata: Dict[str, Any],
    ) -> bool: ...


# Type alias for the factory that produces a ReferenceExtractorProtocol
# instance. Mirrors `app.services.reference_extractor.get_reference_extractor`.
ReferenceExtractorFactory = Callable[[], ReferenceExtractorProtocol]
