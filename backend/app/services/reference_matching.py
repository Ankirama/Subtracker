"""Pure service-reference matching logic.

Leaf module (no I/O, no third-party clients) so both the email-sync dedup
path (`ReferenceExtractor.can_match_subscription`) and the read-only
duplicate-detection endpoint can share a single source of truth for the
matching rule without pulling in the OpenAI client.

The invariant: two subscriptions of the same provider are considered the same
service only if their non-empty ``service_references`` share at least one
identical key/value pair. Empty refs on either side never match.
"""

from typing import Any, Dict


def references_match(refs_a: Dict[str, Any], refs_b: Dict[str, Any]) -> bool:
    """Return True iff two reference dicts share an identical key/value pair.

    Both dicts must be non-empty; an empty (or falsy) dict on either side
    yields False, since we cannot disambiguate without at least one reference.

    Args:
        refs_a: First set of service references (e.g. ``{"domain": "foo.com"}``).
        refs_b: Second set of service references.

    Returns:
        True if at least one key exists in both dicts with an equal value.
    """
    if not refs_a or not refs_b:
        return False

    for key, value in refs_a.items():
        if key in refs_b and refs_b[key] == value:
            return True

    return False
