"""
Multi-strategy duplicate detection for subscription extraction.

Used by the email-sync pipeline to determine, given an extracted subscription
candidate (`extracted_data`) and a pool of existing subscriptions for the same
provider+mailbox (`potential_matches`), which existing subscription (if any)
the candidate should be merged into — or whether a new subscription should be
created (return value `None`).

The 5 strategies are tried in order:

1. Service-reference match: if `extraction_metadata.service_references` is
   non-empty AND a `ref_extractor` is provided, find a `potential_match` whose
   own `extraction_metadata` matches via `ref_extractor.can_match_subscription`.
   If service refs are present but no match is found, return `None` (CRITICAL
   FIX: do NOT fall back to looser strategies — different services from the
   same provider should not be merged, e.g. different OVH services).

2. Single-match assumption: if NO service refs AND `len(potential_matches) == 1`,
   return that single match.

3. Payment-processor heuristic: if `email_sender` contains one of
   PAYMENT_PROCESSOR_KEYWORDS (paypal/stripe/paddle/gumroad/fastspring), return
   `potential_matches[0]` (first/oldest). Payment processors don't reliably
   disambiguate.

4. Email-sender exact match: if one of `potential_matches` has the same
   `.email_sender` as the candidate, return it.

5. Meaningful custom-label match: if the candidate's `custom_label` contains
   one of MEANINGFUL_LABEL_KEYWORDS (tier/channel/plan/premium/basic/pro/plus/
   family/individual/student) AND a `potential_match` has the same
   `.custom_label`, return it.

6. Fallback: return `potential_matches[0]` (first/oldest).

Pure function: no DB queries, no I/O. The `ref_extractor` is injected to keep
this module a leaf in the import DAG.
"""

PAYMENT_PROCESSOR_KEYWORDS = (
    "paypal",
    "stripe",
    "paddle",
    "gumroad",
    "fastspring",
)

MEANINGFUL_LABEL_KEYWORDS = (
    "tier",
    "channel",
    "plan",
    "premium",
    "basic",
    "pro",
    "plus",
    "family",
    "individual",
    "student",
)


def find_best_match(
    extracted_data: dict,
    potential_matches: list,
    *,
    ref_extractor=None,
):
    """Return the best-matching existing subscription, or None if none qualifies.

    See module docstring for the 5-strategy ordering.

    Args:
        extracted_data: dict with keys 'email_sender', 'custom_label',
            'extraction_metadata' (with optional 'service_references').
        potential_matches: list of existing Subscription ORM instances (or
            mocks with .email_sender, .custom_label, .extraction_metadata
            attributes) for the same provider+mailbox.
        ref_extractor: optional service-reference matcher with method
            `can_match_subscription(service_refs: dict, metadata: dict) -> bool`.

    Returns:
        The matching Subscription instance, or None.
    """
    if not potential_matches:
        return None

    extraction_metadata = extracted_data.get("extraction_metadata") or {}
    service_references = extraction_metadata.get("service_references") or {}

    # Strategy 1: service-reference match
    if service_references and ref_extractor is not None:
        for match in potential_matches:
            match_metadata = match.extraction_metadata or {}
            if ref_extractor.can_match_subscription(service_references, match_metadata):
                return match
        # Service refs present but no match → return None (don't fall back)
        return None

    # Strategy 2: single-match assumption (only if no service refs)
    if not service_references and len(potential_matches) == 1:
        return potential_matches[0]

    # If service refs are present but ref_extractor is None, the strategy
    # 1 block above didn't run; still skip strategies 2-6 to honour the
    # "don't merge different services" invariant.
    if service_references:
        return None

    # Below: 2+ matches and no service refs. Try disambiguation.
    email_sender = extracted_data.get("email_sender", "") or ""
    custom_label = extracted_data.get("custom_label", "") or ""

    # Strategy 3: payment-processor heuristic
    is_payment_processor_email = any(
        keyword in email_sender.lower() for keyword in PAYMENT_PROCESSOR_KEYWORDS
    )
    if is_payment_processor_email:
        return potential_matches[0]

    # Strategy 4: email-sender exact match
    for match in potential_matches:
        if match.email_sender == email_sender:
            return match

    # Strategy 5: meaningful custom-label match
    if custom_label:
        is_meaningful = any(
            keyword in custom_label.lower() for keyword in MEANINGFUL_LABEL_KEYWORDS
        )
        if is_meaningful:
            for match in potential_matches:
                if match.custom_label == custom_label:
                    return match

    # Strategy 6: fallback
    return potential_matches[0]
