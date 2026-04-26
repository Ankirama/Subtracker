# C1 Phase 2 — Extract `dedup_strategy.py` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the multi-strategy duplicate-detection logic from `_sync_mailbox_async` (`backend/app/tasks/email_sync.py` lines ~441-577, ~135 LoC) into a dedicated, unit-tested module `backend/app/services/dedup_strategy.py`. Replace the inline block with a one-line delegation. Verified by Phase 1 chartests staying green.

**Scope adjustment from audit (deliberate):** The audit (§A.2 + §B Phase 2) suggested also consolidating logic from `api/subscriptions.py:find_duplicate_subscriptions` (~71 LoC) and exposing a `score_duplicate_pair` helper. On closer reading, that function uses **flat O(n) grouping by `(provider.lower(), billing_cycle)` only** — no multi-strategy matching, no scoring matrix. The two call sites do not share enough logic to justify combining them. **This phase narrows the audit's scope to extracting only §2's multi-strategy logic.** §1's grouping helper stays inline (YAGNI). The audit's §A.2 estimate (~186 LoC consolidated) was overstated; actual consolidation is ~135 LoC. The audit doc will be updated with a footnote in a follow-up PR (out of scope here).

**Architecture:** New module `backend/app/services/dedup_strategy.py` exposes one pure function:

```python
def find_best_match(
    extracted_data: dict,
    potential_matches: list[Subscription],
    *,
    ref_extractor=None,
) -> Optional[Subscription]:
    ...
```

It applies the 5 dedup strategies in order, identical to the existing inline behaviour locked in by Phase 1's `TestSyncInnerPipelineDedup`:

1. Service-reference match (if `extracted_data["extraction_metadata"]["service_references"]` is non-empty AND `ref_extractor` is provided)
2. Single-match assumption (no service refs AND `len(potential_matches) == 1`)
3. Payment-processor heuristic (`extracted_data["email_sender"]` contains `paypal` / `stripe` / `paddle` / `gumroad` / `fastspring`)
4. Email-sender exact match (one of `potential_matches` has the same `.email_sender`)
5. Meaningful custom-label match (one of `potential_matches` has a matching `.custom_label` containing keywords like `tier`, `channel`, `premium`, etc.)
6. Fallback: `potential_matches[0]`

The function is a pure function — no DB writes, no I/O. The `ref_extractor` is injected to avoid the function importing it (keeps the module a leaf in the import DAG).

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 (`Subscription` ORM model — used by type hint only, function does not query), pytest 7.4+.

**Source:**
- Audit: `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` §B Phase 2 (with scope adjustment above).
- Existing chartests: `backend/tests/test_email_sync.py::TestSyncInnerPipelineDedup` (5 tests in Phase 1).

**Branch:** `feat/c1.2-dedup-strategy` (already created from `origin/main`).

---

## Methodology Note: TDD for a Pure Refactor

Phase 2 is a "move + delegate" refactor of behaviour that's already covered by Phase 1's chartests. The TDD discipline still applies for the NEW module's unit tests:

1. Write the failing unit test for `find_best_match`.
2. Run it. Expect FAIL with `ModuleNotFoundError` or `AttributeError` (function doesn't exist yet).
3. Implement `find_best_match` minimally.
4. Run the test. Expect PASS.
5. Repeat for each of the 5 strategies.

After the new module is fully tested, the §2 inline block delegation step is verified by **Phase 1's existing `TestSyncInnerPipelineDedup` (5 tests) staying green**. Those are the integration tests for the dedup logic. If any of them fail after the delegation, the extraction has broken behaviour — fix and re-test.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `backend/app/services/dedup_strategy.py` | Create | Pure-function `find_best_match` + module-level constants (`PAYMENT_PROCESSOR_KEYWORDS`, `MEANINGFUL_LABEL_KEYWORDS`) |
| `backend/tests/test_dedup_strategy.py` | Create | Unit tests for `find_best_match` covering all 5 strategies + edge cases |
| `backend/app/tasks/email_sync.py` | Modify | Replace lines ~441-577 with `existing_sub = find_best_match(subscription_data, potential_matches, ref_extractor=...)`. Add the import at top. |

No production code outside `tasks/email_sync.py` is modified. No existing tests are modified.

---

## Tasks

### Task 1: Create `dedup_strategy.py` with TDD-driven unit tests

**Files:**
- Create: `backend/app/services/dedup_strategy.py`
- Create: `backend/tests/test_dedup_strategy.py`

This task uses true TDD: write each unit test, verify it fails, implement the minimal code, verify it passes, repeat.

- [ ] **Step 1: Write the test file with the first failing test (smoke + service-reference strategy)**

Create `backend/tests/test_dedup_strategy.py`:

```python
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


def _make_sub(*, provider="Netflix", amount=15.99, billing_cycle="monthly",
              email_sender=None, custom_label="", extraction_metadata=None):
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
        target = _make_sub(extraction_metadata={"service_references": {"account_id": "ABC"}})
        other = _make_sub(extraction_metadata={"service_references": {"account_id": "XYZ"}})

        ref_extractor = MagicMock()
        ref_extractor.can_match_subscription.side_effect = (
            lambda refs, metadata: metadata.get("service_references", {}).get("account_id") == "ABC"
        )

        result = find_best_match(
            _ext(extraction_metadata={"service_references": {"account_id": "ABC"}}),
            [other, target],  # target is second; ensure it's preferred over [0] fallback
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
    @pytest.mark.parametrize("processor", ["paypal", "stripe", "paddle", "gumroad", "fastspring"])
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
    @pytest.mark.parametrize("keyword", [
        "tier", "channel", "plan", "premium", "basic", "pro", "plus",
        "family", "individual", "student",
    ])
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
```

- [ ] **Step 2: Run the tests — they should FAIL with ModuleNotFoundError**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_dedup_strategy.py -v
```

Expected: ERRORS like `ModuleNotFoundError: No module named 'app.services.dedup_strategy'`. This confirms the test file is correctly importing the not-yet-existing module.

- [ ] **Step 3: Create the module with the implementation**

Create `backend/app/services/dedup_strategy.py`:

```python
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

from typing import Optional


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
```

- [ ] **Step 4: Run the tests — they should ALL PASS**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_dedup_strategy.py -v
```

Expected: all tests pass (~16 tests across 7 test classes including parametrize expansions).

If any FAIL: read the failure carefully. The test was authored from the inline §2 code's observed behaviour — if a test fails, EITHER the test misread the inline code OR the implementation has a bug. Check the inline code (`backend/app/tasks/email_sync.py` lines ~441-577) to settle the ambiguity, fix whichever is wrong, re-run.

- [ ] **Step 5: Lint**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m black --check app/services/dedup_strategy.py tests/test_dedup_strategy.py
docker-compose -f docker-compose.dev.yml exec -T backend python -m flake8 app/services/dedup_strategy.py tests/test_dedup_strategy.py --max-line-length=120
```

If black fails: `python -m black app/services/dedup_strategy.py tests/test_dedup_strategy.py`. flake8 errors block.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/dedup_strategy.py backend/tests/test_dedup_strategy.py
git commit -m "$(cat <<'EOF'
feat(services): add dedup_strategy.find_best_match (C1 Phase 2)

Pure-function module extracting the multi-strategy duplicate-detection
logic that today lives inline in tasks/email_sync.py:441-577.

Strategies (in order):
1. Service-reference match (if ref_extractor + refs present)
2. Single-match assumption (1 sub, no refs)
3. Payment-processor heuristic (paypal/stripe/etc. sender)
4. Email-sender exact match
5. Meaningful custom-label match (tier/channel/premium/etc.)
6. Fallback (potential_matches[0])

Includes 16 unit tests covering all strategies, the service-ref
"don't fall back" invariant, the parametrized payment-processor
keywords, and the parametrized meaningful-label keywords.

The §2 inline block delegation lands in Task 2.

Part of C1 Phase 2 — see audit §B.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Replace the §2 inline block with a delegation

**Files:**
- Modify: `backend/app/tasks/email_sync.py` (replace lines ~441-577 with delegation; add import at top)

This is a structural change to production code. Phase 1's `TestSyncInnerPipelineDedup` (5 tests) is the integration test that verifies the delegation does not break behaviour.

- [ ] **Step 1: Locate the exact line range to replace**

```bash
grep -n 'is_payment_processor_email\|service_references\|potential_matches' backend/app/tasks/email_sync.py | head
```

Confirm the inline block starts around the comment `# NORMAL PROCESSING: Check if subscription already exists` and ends just before `subscription_record = None` (the dispatch on whether `existing_sub` was found).

Use `Read` with offset/limit to get the EXACT line range. The block is approximately lines 441-577 but may have shifted slightly. The replacement boundary is:

- **START of replacement**: the comment `# NORMAL PROCESSING: Check if subscription already exists` (line ~441)
- **END of replacement**: the line just BEFORE `subscription_record = None` (line ~577)

The `# Primary match: Just provider + mailbox (most forgiving)` block (the `base_query` and `potential_matches = base_query.all()` setup) IS part of the replacement — `find_best_match` does not query the DB, so the caller still needs to materialise `potential_matches` before calling. Keep the `base_query` and `potential_matches.all()` lines in place. **Replace only the strategy logic itself**, not the DB query.

After clarification: the START of replacement is the comment `# NORMAL PROCESSING: Check if subscription already exists` — but the FIRST replacement-target line is `existing_sub = None` (just after `potential_matches = base_query.all()`). The DB query stays.

Re-examine the source carefully to confirm. Adjust the boundary if the actual line numbers differ.

- [ ] **Step 2: Add the import at the top of `tasks/email_sync.py`**

Find the existing imports block and add (alphabetically sorted within the `app.services.*` group):

```python
from app.services.dedup_strategy import find_best_match
```

If `app.services.reference_extractor` is already imported at module level, place the new import alphabetically. If `reference_extractor` is imported inline (inside the function), the new import goes at module level — do NOT keep it inline, since `find_best_match` itself is now the entry point.

- [ ] **Step 3: Replace the inline block with a delegation**

The replacement reduces the strategy logic to a single function call. The exact lines around the boundary must be preserved (comments, the `base_query` build, the `potential_matches.all()` call, and the post-match dispatch on `existing_sub`).

The replacement looks like:

```python
                        # NORMAL PROCESSING: Check if subscription already exists
                        # See app/services/dedup_strategy.py for the strategy ordering.
                        # Strategies: service-ref → single-match → payment-processor →
                        # email-sender → meaningful custom-label → fallback.

                        # Primary match: Just provider + mailbox (most forgiving)
                        base_query = db.query(Subscription).filter(
                            Subscription.mailbox_id == mailbox.id,
                            Subscription.provider == subscription_data["provider"],
                        )
                        potential_matches = base_query.all()

                        # Lazy import — get_reference_extractor is itself a factory
                        # function, not the class, so this stays cheap.
                        from app.services.reference_extractor import get_reference_extractor
                        ref_extractor = get_reference_extractor()

                        existing_sub = find_best_match(
                            subscription_data,
                            potential_matches,
                            ref_extractor=ref_extractor,
                        )
```

Use `Edit` with the EXACT old_string capturing the entire replaced block (~135 lines). The new_string is the ~20 lines above. The implementer must read the file precisely to capture the old_string verbatim — any whitespace mismatch will fail the Edit.

If the existing code already imports `get_reference_extractor` at module level (check the top of the file), drop the inner `from app.services.reference_extractor import get_reference_extractor` line.

- [ ] **Step 4: Verify Phase 1 dedup chartests still pass**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineDedup -v
```

Expected: `5 passed`.

If any test FAILS: the delegation has changed observable behaviour. Read the failing test, compare its setup to what the inline code did vs what `find_best_match` does. Adjust either the `find_best_match` implementation (more likely — there's a subtle behaviour difference we missed) or the call site (less likely).

DO NOT change the chartest itself. Phase 1's chartests are the contract.

- [ ] **Step 5: Run the full email_sync test class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py -v
```

Expected: all email_sync tests pass (TestParseDateFilter, TestUpdateSubscriptionStatuses, TestSyncMailboxEmails, plus all 5 Phase 1 inner-pipeline classes including the dedup one).

- [ ] **Step 6: Run the new dedup_strategy unit tests too**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_dedup_strategy.py tests/test_email_sync.py::TestSyncInnerPipelineDedup -v
```

Expected: all pass — the unit tests + the integration tests both green confirms the delegation is clean.

- [ ] **Step 7: Lint**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m black --check app/tasks/email_sync.py
docker-compose -f docker-compose.dev.yml exec -T backend python -m flake8 app/tasks/email_sync.py --max-line-length=120
```

If black fails: auto-fix.

- [ ] **Step 8: Verify line-count reduction**

```bash
git diff origin/main..HEAD -- backend/app/tasks/email_sync.py | grep '^-' | wc -l
git diff origin/main..HEAD -- backend/app/tasks/email_sync.py | grep '^+' | wc -l
```

Expected: net negative ~110 lines (135 removed, ~20-25 added back as the delegation). Document this in the commit message.

- [ ] **Step 9: Commit**

```bash
git add backend/app/tasks/email_sync.py
git commit -m "$(cat <<'EOF'
refactor(tasks): delegate dedup logic in email_sync to dedup_strategy

Replaces the inline ~135-LoC multi-strategy block in
_sync_mailbox_async with a 1-call delegation to
app.services.dedup_strategy.find_best_match. Net reduction: ~110 lines.

The 5 dedup strategies (service-ref, single-match, payment-processor,
email-sender, custom-label, fallback) are now unit-tested in isolation
(see tests/test_dedup_strategy.py). Behaviour is preserved end-to-end,
verified by Phase 1's TestSyncInnerPipelineDedup (5 chartests, all green).

Part of C1 Phase 2 — see audit §B.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Final verification, lint, push, and PR

- [ ] **Step 1: Run all tests touching this PR's scope**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest \
  tests/test_dedup_strategy.py \
  tests/test_email_sync.py \
  tests/test_subscriptions_api.py \
  -v
```

Expected: all pass — the new unit tests + the existing email_sync tests (Phase 1 chartests + pre-Phase 1 ones) + the §1 chartests from Phase 1.

- [ ] **Step 2: Verify no other production code touched**

```bash
git diff origin/main..HEAD --stat -- backend/app/
```

Expected: only `backend/app/services/dedup_strategy.py` (created) and `backend/app/tasks/email_sync.py` (modified). No other production files.

- [ ] **Step 3: Final lint**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m black --check app/ tests/
docker-compose -f docker-compose.dev.yml exec -T backend python -m flake8 app/ tests/ --max-line-length=120
```

Expected: clean. flake8 errors block; warnings tolerated.

- [ ] **Step 4: Commit-history check**

```bash
git log --oneline origin/main..HEAD
```

Expected: 2 commits (Task 1 + Task 2) plus any black-format commit if needed. Subjects scoped (`feat(services):`, `refactor(tasks):`).

- [ ] **Step 5: Push**

```bash
git push -u origin feat/c1.2-dedup-strategy
```

- [ ] **Step 6: Create the PR**

```bash
gh pr create --title "refactor(C1.2): extract dedup_strategy.py from email_sync inner pipeline" --body "$(cat <<'EOF'
## Summary

C1 Phase 2 (audit §B): extracts the multi-strategy duplicate-detection logic from `_sync_mailbox_async` (`tasks/email_sync.py:~441-577`, ~135 LoC) into a dedicated, unit-tested module `services/dedup_strategy.py`. The §2 inline block becomes a one-call delegation. Phase 1's `TestSyncInnerPipelineDedup` (5 integration chartests) remains green, confirming behaviour is preserved.

### What landed

- **NEW** `backend/app/services/dedup_strategy.py` — pure function `find_best_match(extracted_data, potential_matches, *, ref_extractor=None)`.
- **NEW** `backend/tests/test_dedup_strategy.py` — 16 unit tests covering all 5 dedup strategies, the service-ref "don't fall back" invariant, parametrized payment-processor + meaningful-label keywords.
- **MODIFIED** `backend/app/tasks/email_sync.py` — replaced ~135 LoC inline block with a delegation. Net reduction: ~110 lines.

### Scope adjustment from audit

The audit's §A.2 + §B Phase 2 suggested also consolidating logic from `api/subscriptions.py:find_duplicate_subscriptions` (~71 LoC) and adding a `score_duplicate_pair` helper. On closer reading during planning, that function uses **flat O(n) grouping by `(provider.lower(), billing_cycle)` only** — no multi-strategy matching, no scoring matrix. The two call sites do not share enough logic to justify combining them. **This PR narrows the audit's scope to extracting only §2's multi-strategy logic.** §1's grouping helper stays inline (YAGNI). The audit's §A.2 estimate of ~186 consolidated LoC was overstated; actual is ~135.

### Why this is safe

- Phase 1's `TestSyncInnerPipelineDedup` (5 chartests) covers all 5 strategies end-to-end through `sync_mailbox_emails`. They stay green.
- The new `find_best_match` is a pure function (no DB, no I/O). 16 unit tests cover its branches in isolation.
- `ref_extractor` is injected, keeping the new module a leaf in the import DAG.

## Test plan

- [ ] `pytest tests/test_dedup_strategy.py -v` → 16 passed
- [ ] `pytest tests/test_email_sync.py::TestSyncInnerPipelineDedup -v` → 5 passed
- [ ] `pytest tests/test_email_sync.py -v` → all email_sync tests pass
- [ ] `pytest tests/test_subscriptions_api.py -v` → all §1 chartests still pass
- [ ] `git diff origin/main..HEAD --stat -- backend/app/` → only `services/dedup_strategy.py` + `tasks/email_sync.py`
- [ ] black + flake8 pass on `app/` and `tests/`
- [ ] Decide: ready to start C1 Phase 3 (`EmailService` singleton kill)?

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 7: Surface a one-line summary** with PR URL, commit count, pass count.

---

## Self-Review (already performed)

- **Spec coverage**: audit §B Phase 2 requirements:
  - "Create `dedup_strategy.py` with consolidated API" → Task 1 ✓
  - "Replace `find_duplicate_subscriptions` body in `api/subscriptions.py`" → **DEFERRED** (scope adjustment documented in plan + PR body — §1's grouping pattern doesn't share enough with §2 to consolidate)
  - "Replace the multi-strategy block in `_sync_mailbox_async`" → Task 2 ✓
  - "Re-run Phase 1 chartests. They must pass unchanged" → Task 2 Step 4 ✓
- **Placeholder scan**: no `TBD`, `TODO`, or `pytest.skip`. Test code is concrete. The implementation is concrete. Commit messages are templates with explicit replacement notes only where needed.
- **Type / name consistency**: `find_best_match`, `extracted_data`, `potential_matches`, `ref_extractor` used identically across module, tests, and call site. Constants `PAYMENT_PROCESSOR_KEYWORDS` and `MEANINGFUL_LABEL_KEYWORDS` named consistently.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-25-c1-phase-2-dedup-strategy.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session via `superpowers:executing-plans`.

Which approach?
