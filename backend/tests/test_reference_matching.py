"""Unit tests for app.services.reference_matching.references_match.

Locks in the shared matching rule: two non-empty reference dicts match iff
they share at least one identical key/value pair.
"""

from app.services.reference_matching import references_match


class TestReferencesMatch:
    def test_overlapping_pair_matches(self):
        assert references_match({"domain": "foo.com"}, {"domain": "foo.com"}) is True

    def test_overlap_among_multiple_keys_matches(self):
        a = {"domain": "foo.com", "invoice_number": "INV-1"}
        b = {"domain": "foo.com", "invoice_number": "INV-9"}
        assert references_match(a, b) is True

    def test_same_key_different_value_does_not_match(self):
        assert (
            references_match({"domain": "www.ovh"}, {"domain": "www.paypalobjects"})
            is False
        )

    def test_disjoint_keys_do_not_match(self):
        assert (
            references_match({"domain": "foo.com"}, {"channel_name": "twitch"}) is False
        )

    def test_empty_left_does_not_match(self):
        assert references_match({}, {"domain": "foo.com"}) is False

    def test_empty_right_does_not_match(self):
        assert references_match({"domain": "foo.com"}, {}) is False

    def test_both_empty_does_not_match(self):
        assert references_match({}, {}) is False

    def test_ovh_real_case_not_matched(self):
        """OVH: two subs with different domains must not match."""
        a = {"domain": "www.ovh"}
        b = {"domain": "www.paypalobjects"}
        assert references_match(a, b) is False

    def test_twitch_real_case_ref_vs_noref(self):
        """A ref-bearing sub vs a no-ref sub never matches."""
        assert references_match({"channel_name": "twitch"}, {}) is False
