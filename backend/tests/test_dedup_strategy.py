"""
Unit tests for app.services.dedup_strategy.find_best_match.

Locks in the 5 dedup strategies in execution order:
1. Service-reference match
2. Single-match assumption
3. Payment-processor heuristic
4. Email-sender exact match
5. Meaningful custom-label match
6. Fallback (potential_matches[0])
"""

from unittest.mock import MagicMock

import pytest

from app.services.dedup_strategy import find_best_match


def _make_sub(
    *,
    provider="Netflix",
    amount=15.99,
    billing_cycle="monthly",
    email_sender=None,
    custom_label="",
    extraction_metadata=None,
):
    """Build a Subscription-like object for the function under test."""
    sub = MagicMock()
    sub.provider = provider
    sub.amount = amount
    sub.billing_cycle = billing_cycle
    sub.email_sender = email_sender
    sub.custom_label = custom_label
    sub.extraction_metadata = extraction_metadata or {}
    return sub


def _ext(**overrides):
    """Build an extracted_data dict with sensible defaults."""
    base = {
        "provider": "Netflix",
        "amount": 15.99,
        "currency": "EUR",
        "billing_cycle": "monthly",
        "email_sender": "billing@netflix.com",
        "custom_label": "",
        "extraction_metadata": {"service_references": {}},
    }
    base.update(overrides)
    return base


class TestFindBestMatchEmptyPool:
    def test_returns_none_when_no_potential_matches(self):
        result = find_best_match(_ext(), [], ref_extractor=None)
        assert result is None


class TestFindBestMatchServiceReferenceStrategy:
    def test_returns_match_when_ref_extractor_matches(self):
        """Strategy 1: service references present + ref_extractor matches → that sub wins."""
        target = _make_sub(
            extraction_metadata={"service_references": {"account_id": "ABC"}}
        )
        other = _make_sub(
            extraction_metadata={"service_references": {"account_id": "XYZ"}}
        )

        ref_extractor = MagicMock()
        ref_extractor.can_match_subscription.side_effect = (
            lambda refs, metadata: metadata.get("service_references", {}).get(
                "account_id"
            )
            == "ABC"
        )

        result = find_best_match(
            _ext(extraction_metadata={"service_references": {"account_id": "ABC"}}),
            [
                other,
                target,
            ],  # target is second; ensure it's preferred over [0] fallback
            ref_extractor=ref_extractor,
        )
        assert result is target

    def test_returns_none_when_service_refs_present_but_no_match(self):
        """Strategy 1 anomaly: service refs present, no ref_extractor match → returns None
        (the inline §2 code creates a NEW subscription rather than falling back).
        Lock this 'CRITICAL FIX' invariant explicitly."""
        sub = _make_sub()
        ref_extractor = MagicMock()
        ref_extractor.can_match_subscription.return_value = False

        result = find_best_match(
            _ext(extraction_metadata={"service_references": {"account_id": "ABC"}}),
            [sub],
            ref_extractor=ref_extractor,
        )
        assert result is None

    def test_skips_service_ref_strategy_when_ref_extractor_is_none(self):
        """When ref_extractor is None and service refs are present, the strategy is
        skipped (next strategies apply)."""
        sub = _make_sub()
        result = find_best_match(
            _ext(extraction_metadata={"service_references": {"account_id": "ABC"}}),
            [sub],
            ref_extractor=None,
        )
        # With service refs present + no ref_extractor + 1 sub: inline code falls
        # through to the single-match assumption, which itself is gated on
        # `not service_references`. So no match — returns None.
        assert result is None


class TestFindBestMatchSingleMatchStrategy:
    def test_returns_only_match_when_no_service_refs(self):
        """Strategy 2: 1 potential match + no service refs → returns it."""
        sub = _make_sub()
        result = find_best_match(_ext(), [sub], ref_extractor=None)
        assert result is sub


class TestFindBestMatchPaymentProcessorStrategy:
    @pytest.mark.parametrize(
        "processor", ["paypal", "stripe", "paddle", "gumroad", "fastspring"]
    )
    def test_uses_first_match_when_email_from_payment_processor(self, processor):
        """Strategy 3: 2+ matches, email from payment processor → first sub wins."""
        sub_a = _make_sub(provider="OVH")
        sub_b = _make_sub(provider="OVH")
        sub_c = _make_sub(provider="OVH")
        result = find_best_match(
            _ext(provider="OVH", email_sender=f"service@{processor}.com"),
            [sub_a, sub_b, sub_c],
            ref_extractor=None,
        )
        assert result is sub_a

    def test_payment_processor_is_case_insensitive(self):
        sub_a = _make_sub(provider="OVH")
        sub_b = _make_sub(provider="OVH")
        result = find_best_match(
            _ext(provider="OVH", email_sender="service@PayPal.com"),
            [sub_a, sub_b],
            ref_extractor=None,
        )
        assert result is sub_a


class TestFindBestMatchEmailSenderStrategy:
    def test_disambiguates_by_email_sender_exact_match(self):
        """Strategy 4: 2+ non-payment-processor matches, one has matching email_sender → that one wins."""
        sub_a = _make_sub(email_sender="streamerA@twitch.tv")
        sub_b = _make_sub(email_sender="streamerB@twitch.tv")
        result = find_best_match(
            _ext(provider="Netflix", email_sender="streamerB@twitch.tv"),
            [sub_a, sub_b],
            ref_extractor=None,
        )
        assert result is sub_b


class TestFindBestMatchCustomLabelStrategy:
    @pytest.mark.parametrize(
        "keyword",
        [
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
        ],
    )
    def test_disambiguates_by_meaningful_custom_label(self, keyword):
        """Strategy 5: 2+ matches, no email_sender match, candidate has meaningful label → label-match wins."""
        target_label = f"my {keyword} subscription"
        sub_a = _make_sub(email_sender="x@a.com", custom_label="other label")
        sub_b = _make_sub(email_sender="x@a.com", custom_label=target_label)
        result = find_best_match(
            _ext(email_sender="other@b.com", custom_label=target_label),
            [sub_a, sub_b],
            ref_extractor=None,
        )
        assert result is sub_b

    def test_skips_label_match_when_label_lacks_keywords(self):
        """Custom label without meaningful keyword → not used for matching, falls through to fallback."""
        sub_a = _make_sub(email_sender="x@a.com", custom_label="my_random_note")
        sub_b = _make_sub(email_sender="x@a.com", custom_label="another_note")
        result = find_best_match(
            _ext(email_sender="other@b.com", custom_label="my_random_note"),
            [sub_a, sub_b],
            ref_extractor=None,
        )
        # Falls through to fallback (potential_matches[0])
        assert result is sub_a


class TestFindBestMatchFallback:
    def test_falls_back_to_first_match_when_nothing_else_applies(self):
        """Strategy 6: 2+ matches, no other strategy fires → potential_matches[0] wins."""
        sub_a = _make_sub(email_sender="x@a.com", custom_label="")
        sub_b = _make_sub(email_sender="y@b.com", custom_label="")
        result = find_best_match(
            _ext(email_sender="other@c.com", custom_label=""),
            [sub_a, sub_b],
            ref_extractor=None,
        )
        assert result is sub_a
