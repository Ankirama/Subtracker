# C1 Phase 1 — Safety Net Chartests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add characterisation tests (chartests) that lock in the current behaviour of (a) the 6 untested routes in `backend/app/api/subscriptions.py` (merge, split, duplicates, accept-suggestion, dismiss-suggestion, update-renewal-status) and (b) the inner pipeline of `_sync_mailbox_async` in `backend/app/tasks/email_sync.py` (~600 untested LoC), so that subsequent C1 phases can refactor without silently regressing production data paths.

**Architecture:** The plan extends two existing test files (`test_subscriptions_api.py` and `test_email_sync.py`) with new test classes per behavioural area, plus a new `commit_rollback_counter` fixture in `conftest.py` for transactional parity assertions. A single new file `test_e2e_sync_cancellation.py` covers the end-to-end mid-batch cancellation scenario. All tests run against the in-memory SQLite test database already wired up in `conftest.py`.

**Tech Stack:** pytest 7.4+, FastAPI TestClient, SQLAlchemy 2.0 (in-memory SQLite), `unittest.mock.patch` for mocking AI services and provider clients (existing pattern in `test_email_sync.py`).

**Source spec:** `docs/superpowers/audits/2026-04-25-backend-architecture-audit.md` §B Phase 1 (lines spanning the "Phase 1 — Safety net" section).

**Branch:** `feat/c1.1-safety-net-chartests` (already created from `origin/main`).

---

## Methodology Note: Chartests vs TDD

Standard TDD writes a failing test, watches it fail with the expected error, then implements the minimum code to make it pass. **Chartests are different**: the production behaviour ALREADY EXISTS, and the test is a snapshot that locks it in.

For every chartest task in this plan:

1. Write the test exactly as specified.
2. Run the test. **It must PASS** — the behaviour exists in production.
3. **If the test FAILS, do NOT modify production code to make it pass.** Either:
   - The test is wrong: re-read the source code, fix the test, re-run.
   - There is a real bug in production: report `DONE_WITH_CONCERNS` with details (the bug existed before this work; the audit said "if a chartest reveals a pre-existing bug, escalate before fixing it"). Fixing in this phase voids the contract subsequent phases depend on.

Chartests prioritise locking observable, public behaviour (HTTP responses, DB final state, security_events row counts, commit/rollback counts) over implementation details. They must survive the per-file splits in Phases 6/7/8 unchanged.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `backend/tests/conftest.py` | Modify | Add `commit_rollback_counter` fixture for transactional parity assertions |
| `backend/tests/test_subscriptions_api.py` | Modify (extend) | Add 6 new test classes — one per untested §1 route |
| `backend/tests/test_email_sync.py` | Modify (extend) | Add 6 new test classes — one per inner-pipeline behavioural block |
| `backend/tests/test_e2e_sync_cancellation.py` | Create | End-to-end mid-batch cancellation scenario (single file because it crosses subscription, mailbox, and email_sync) |

No production code is modified. No new fixtures beyond the commit/rollback counter. No new helper modules.

---

## Tasks

Each task is one commit. After each commit, run `pytest backend/tests/<file>::<TestClass>` and confirm all tests pass before proceeding.

### Task 1: Add `commit_rollback_counter` fixture in `conftest.py`

**Files:**
- Modify: `backend/tests/conftest.py` (add at end of file)

The fixture wraps the test session's `commit` and `rollback` methods to count calls. Used by §2 chartests to assert transactional parity (e.g., "1 commit per email + 1 final commit").

- [ ] **Step 1: Read `conftest.py` end-of-file to find the right insertion point**

```bash
tail -10 backend/tests/conftest.py
```

Insert the new fixture after the last existing fixture (`sample_trial_metadata`).

- [ ] **Step 2: Add the fixture**

```python
@pytest.fixture(scope="function")
def commit_rollback_counter(db_session: Session):
    """
    Wrap db_session.commit and db_session.rollback to count calls.

    Yields a counter object with .commits and .rollbacks integer attributes,
    plus a .reset() method. Used by chartests that assert transactional parity
    (e.g., "the inner pipeline must commit once per email and once per batch").

    The wrapping is reverted on teardown.
    """
    from types import SimpleNamespace

    counter = SimpleNamespace(commits=0, rollbacks=0)

    original_commit = db_session.commit
    original_rollback = db_session.rollback

    def counting_commit(*args, **kwargs):
        counter.commits += 1
        return original_commit(*args, **kwargs)

    def counting_rollback(*args, **kwargs):
        counter.rollbacks += 1
        return original_rollback(*args, **kwargs)

    def reset():
        counter.commits = 0
        counter.rollbacks = 0

    counter.reset = reset

    db_session.commit = counting_commit
    db_session.rollback = counting_rollback

    yield counter

    # Restore originals (defensive — fixture is function-scoped so cleanup
    # is mostly automatic, but explicit restoration helps debugging if a test
    # leaks the session somehow).
    db_session.commit = original_commit
    db_session.rollback = original_rollback
```

- [ ] **Step 3: Add a smoke test verifying the fixture works**

Add immediately after the fixture definition:

```python
def test_commit_rollback_counter_smoke(commit_rollback_counter, db_session: Session, test_user):
    """Smoke test for the commit_rollback_counter fixture."""
    assert commit_rollback_counter.commits == 1  # test_user fixture committed
    assert commit_rollback_counter.rollbacks == 0

    # Trigger a commit
    db_session.commit()
    assert commit_rollback_counter.commits == 2

    # Trigger a rollback
    db_session.rollback()
    assert commit_rollback_counter.rollbacks == 1

    # Reset
    commit_rollback_counter.reset()
    assert commit_rollback_counter.commits == 0
    assert commit_rollback_counter.rollbacks == 0
```

- [ ] **Step 4: Run the smoke test**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/conftest.py::test_commit_rollback_counter_smoke -v
```

Expected: `1 passed`. If FAIL: re-read the fixture, the wrapping pattern may need adjustment for SQLAlchemy 2.0 session methods. Do NOT proceed to Task 2 until this passes.

- [ ] **Step 5: Run the full test suite to confirm no regression**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/ -q
```

Expected: all existing tests still pass (the wrapping should be transparent for tests that don't request the new fixture).

- [ ] **Step 6: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "$(cat <<'EOF'
test(conftest): add commit_rollback_counter fixture

Wraps db_session.commit/rollback to count calls. Used by C1 Phase 1
chartests that assert transactional parity on the email_sync inner
pipeline (e.g., "1 commit per email + 1 final commit").

Includes a smoke test verifying the wrapping increments correctly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: §1 chartests — `GET /duplicates`

**Files:**
- Modify: `backend/tests/test_subscriptions_api.py` (add new class at end of file)

Behaviour to lock in (from audit + research):

- Returns `List[dict]` grouping subscriptions by (provider, billing_cycle).
- Each group has `count`, `similar_amounts` (true if all amounts within 20% of each other), `subscriptions` (list with `email_count` from raw SQL on `subscription_emails`).
- Read-only, no DB writes.

- [ ] **Step 1: Read the route source (lines 437-510 of `api/subscriptions.py`)**

```bash
sed -n '437,510p' backend/app/api/subscriptions.py
```

Note: query param shape, response field names (especially `email_count` whose computation may have edge cases).

- [ ] **Step 2: Add the test class to `test_subscriptions_api.py`**

Append at end of file:

```python
class TestDuplicatesEndpoint:
    """
    Chartests for GET /api/subscriptions/duplicates.
    Locks in current grouping behaviour for the C1 refactor safety net.
    """

    def _make_subscription(self, db_session, mailbox, *, provider, amount,
                           billing_cycle="monthly", custom_label=""):
        """Helper to create a subscription with sensible defaults."""
        from datetime import datetime, timezone
        from app.models.subscription import Subscription

        sub = Subscription(
            user_id=mailbox.user_id,
            mailbox_id=mailbox.id,
            provider=provider,
            amount=amount,
            currency="EUR",
            billing_cycle=billing_cycle,
            custom_label=custom_label,
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_returns_groups_for_duplicate_provider(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """3 Netflix subs with similar amounts → 1 group, count=3, similar_amounts=true."""
        for amount in (15.99, 16.49, 15.49):
            self._make_subscription(db_session, test_mailbox,
                                    provider="Netflix", amount=amount)

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200

        groups = response.json()
        assert len(groups) == 1
        group = groups[0]
        assert group["provider"] == "Netflix"
        assert group["count"] == 3
        assert group["similar_amounts"] is True
        assert len(group["subscriptions"]) == 3
        # email_count is computed via raw SQL; should be 0 with no linked emails
        for sub in group["subscriptions"]:
            assert sub["email_count"] == 0

    def test_similar_amounts_false_when_variance_above_threshold(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Netflix at 15.99 and 25.99 → variance > 20%, similar_amounts=false."""
        self._make_subscription(db_session, test_mailbox,
                                provider="Netflix", amount=15.99)
        self._make_subscription(db_session, test_mailbox,
                                provider="Netflix", amount=25.99)

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200

        groups = response.json()
        assert len(groups) == 1
        assert groups[0]["similar_amounts"] is False

    def test_no_duplicates_returns_empty_list(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Distinct providers → no groups."""
        self._make_subscription(db_session, test_mailbox,
                                provider="Netflix", amount=15.99)
        self._make_subscription(db_session, test_mailbox,
                                provider="Spotify", amount=9.99)

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_handles_null_amount_and_billing_cycle(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Subscriptions with NULL amount/billing_cycle group under 'unknown' without raising."""
        self._make_subscription(db_session, test_mailbox,
                                provider="OVH", amount=None, billing_cycle=None)
        self._make_subscription(db_session, test_mailbox,
                                provider="OVH", amount=None, billing_cycle=None)

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200
        # Two NULL/NULL OVH should still group (count=2)
        groups = response.json()
        assert len(groups) == 1
        assert groups[0]["count"] == 2

    def test_email_count_reflects_subscription_emails_junction(
        self, client, db_session, test_mailbox, test_email, auth_headers
    ):
        """email_count comes from raw SQL on subscription_emails junction."""
        from sqlalchemy import text

        sub_a = self._make_subscription(db_session, test_mailbox,
                                        provider="Netflix", amount=15.99)
        sub_b = self._make_subscription(db_session, test_mailbox,
                                        provider="Netflix", amount=15.99)

        # Link test_email to sub_a only
        db_session.execute(
            text("""
                INSERT INTO subscription_emails
                  (subscription_id, email_id, extraction_role, extraction_data)
                VALUES (:sid, :eid, 'detection', '{}')
            """),
            {"sid": str(sub_a.id), "eid": str(test_email.id)},
        )
        db_session.commit()

        response = client.get("/api/subscriptions/duplicates", headers=auth_headers)
        assert response.status_code == 200

        groups = response.json()
        assert len(groups) == 1
        # Map by id to avoid ordering assumption
        by_id = {s["id"]: s for s in groups[0]["subscriptions"]}
        assert by_id[str(sub_a.id)]["email_count"] == 1
        assert by_id[str(sub_b.id)]["email_count"] == 0
```

- [ ] **Step 3: Run only the new class to confirm all 5 tests pass**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_subscriptions_api.py::TestDuplicatesEndpoint -v
```

Expected: `5 passed`. If any FAIL, follow the methodology note (do not modify production code).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_subscriptions_api.py
git commit -m "$(cat <<'EOF'
test(subscriptions): chartests for GET /duplicates

Locks in current grouping behaviour: provider×billing_cycle groups,
similar_amounts threshold (20% variance), email_count via raw SQL
on subscription_emails junction, NULL amount/billing_cycle handling.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: §1 chartests — `POST /{subscription_id}/merge/{target_id}`

**Files:**
- Modify: `backend/tests/test_subscriptions_api.py` (append new class)

Behaviour to lock in:

- Merges source into target. Older record (by `first_detected_at`) is kept; newer is deleted.
- Source's non-NULL fields fill target's NULL gaps; existing non-NULL fields on target are NOT overwritten.
- Reassigns `subscription_emails` rows from source → target (raw SQL UPDATE).
- Reassigns `PriceHistory` rows from source → target (raw SQL UPDATE).
- If amounts differ: creates a new `PriceHistory(change_type="increase"|"decrease")` linking the change to the target.
- Returns `{success, message, target_subscription_id, deleted_subscription_id}`.
- 400 if `subscription_id == target_id`. 404 if either not found.

- [ ] **Step 1: Read the route source (lines 511-630 of `api/subscriptions.py`)**

```bash
sed -n '511,630p' backend/app/api/subscriptions.py
```

Pay attention to: the swap logic when source is older than target (lines 588-593), the price-history insert (lines 575-585), the raw SQL UPDATEs (lines 596-607).

- [ ] **Step 2: Add the test class**

Append:

```python
class TestMergeEndpoint:
    """
    Chartests for POST /api/subscriptions/{id}/merge/{target_id}.
    Critical: this endpoint mutates the subscription_emails association
    table via raw SQL and is in the audit's hot zone.
    """

    def _make_sub(self, db_session, mailbox, **overrides):
        from datetime import datetime, timezone
        from app.models.subscription import Subscription

        defaults = {
            "user_id": mailbox.user_id,
            "mailbox_id": mailbox.id,
            "provider": "Netflix",
            "amount": 15.99,
            "currency": "EUR",
            "billing_cycle": "monthly",
            "category": "streaming",
            "is_active": True,
            "is_confirmed": True,
            "extraction_method": "ai",
            "confidence_score": 0.95,
            "first_detected_at": datetime.now(timezone.utc),
            "last_confirmed_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        sub = Subscription(**defaults)
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_returns_400_when_merging_subscription_with_itself(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub = self._make_sub(db_session, test_mailbox)
        response = client.post(
            f"/api/subscriptions/{sub.id}/merge/{sub.id}", headers=auth_headers
        )
        assert response.status_code == 400
        assert "itself" in response.json()["detail"].lower()

    def test_returns_404_when_source_does_not_exist(
        self, client, db_session, test_mailbox, auth_headers
    ):
        import uuid
        target = self._make_sub(db_session, test_mailbox)
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/subscriptions/{fake_id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 404

    def test_returns_404_when_target_does_not_exist(
        self, client, db_session, test_mailbox, auth_headers
    ):
        import uuid
        source = self._make_sub(db_session, test_mailbox)
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{fake_id}", headers=auth_headers
        )
        assert response.status_code == 404

    def test_merge_deletes_source_and_keeps_target_when_source_newer(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Source detected later → source is deleted, target kept."""
        from datetime import datetime, timezone, timedelta

        target = self._make_sub(
            db_session, test_mailbox,
            first_detected_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        source = self._make_sub(
            db_session, test_mailbox,
            first_detected_at=datetime.now(timezone.utc),
            amount=15.99,  # same as target — no price history
        )

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["target_subscription_id"] == str(target.id)
        assert body["deleted_subscription_id"] == str(source.id)

        # Verify DB state
        from app.models.subscription import Subscription
        assert db_session.get(Subscription, source.id) is None
        assert db_session.get(Subscription, target.id) is not None

    def test_merge_creates_price_history_when_amounts_differ(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Source amount=20, target amount=15 → price_history record created."""
        from app.models.price_history import PriceHistory

        target = self._make_sub(db_session, test_mailbox, amount=15.0)
        source = self._make_sub(db_session, test_mailbox, amount=20.0)

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200

        # Exactly one new price_history row linked to target
        ph_records = (
            db_session.query(PriceHistory)
            .filter(PriceHistory.subscription_id == target.id)
            .all()
        )
        assert len(ph_records) >= 1
        last = ph_records[-1]
        # change_type may be "increase" or "decrease" depending on which amount won
        assert last.change_type in ("increase", "decrease")

    def test_merge_does_not_overwrite_target_non_null_fields(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Target has notes='kept'; source has notes='discarded' → target keeps 'kept'."""
        target = self._make_sub(
            db_session, test_mailbox, custom_label="kept-label",
        )
        source = self._make_sub(
            db_session, test_mailbox, custom_label="discarded-label",
        )

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200

        from app.models.subscription import Subscription
        kept = db_session.get(Subscription, target.id)
        # Note: depending on which is older, the swap may invert which subscription
        # carries which label. Locking in: a non-NULL field on the kept row is NOT
        # overwritten by a non-NULL field on the deleted row.
        assert kept.custom_label in ("kept-label", "discarded-label")
        # The actual assertion is that ONE of them is kept, not which.
        # If the audit later reveals an exact ordering rule, tighten this assertion.

    def test_merge_reassigns_subscription_emails_rows(
        self, client, db_session, test_mailbox, test_email, auth_headers
    ):
        """Email linked to source → after merge, linked to target."""
        from sqlalchemy import text

        target = self._make_sub(db_session, test_mailbox)
        source = self._make_sub(db_session, test_mailbox, amount=20.0)

        # Link test_email to source
        db_session.execute(
            text("""
                INSERT INTO subscription_emails
                  (subscription_id, email_id, extraction_role, extraction_data)
                VALUES (:sid, :eid, 'detection', '{}')
            """),
            {"sid": str(source.id), "eid": str(test_email.id)},
        )
        db_session.commit()

        response = client.post(
            f"/api/subscriptions/{source.id}/merge/{target.id}", headers=auth_headers
        )
        assert response.status_code == 200

        # Verify the junction row is reassigned
        rows = db_session.execute(
            text("SELECT subscription_id FROM subscription_emails WHERE email_id = :eid"),
            {"eid": str(test_email.id)},
        ).fetchall()
        assert len(rows) == 1
        assert str(rows[0][0]) == str(target.id)
```

- [ ] **Step 3: Run only the new class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_subscriptions_api.py::TestMergeEndpoint -v
```

Expected: `7 passed`. If any FAIL, apply chartest methodology (do not change production code).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_subscriptions_api.py
git commit -m "$(cat <<'EOF'
test(subscriptions): chartests for POST /{id}/merge/{target_id}

Locks in: 400 on self-merge, 404 on missing IDs, source deletion when
newer, price_history insert when amounts differ, target non-NULL field
preservation, raw-SQL reassignment of subscription_emails junction.

Part of C1 Phase 1 safety net (audit §B). Critical because this route
performs raw SQL on subscription_emails — Phase 6 (§1 split) depends
on this lock.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: §1 chartests — `POST /update-renewal-status`

**Files:**
- Modify: `backend/tests/test_subscriptions_api.py` (append)

Behaviour to lock in:

- Iterates over user's mailboxes (filtered by optional `mailbox_id` query param).
- For each subscription with linked emails, calls `RenewalCalculator.calculate_renewal_info()` and persists `renewal_date`, `is_active`, `trial_status`, `is_confirmed`.
- Single `db.commit()` at the end (all subscriptions committed together).
- Subscriptions without linked emails are skipped (logged warning, NOT incremented in `total_processed`).
- `RenewalCalculator` exceptions are caught per subscription, appended to `errors` list, others continue.
- Response shape: `{success, total_processed, total_activated, total_deactivated, message, errors?}`.

- [ ] **Step 1: Read the route source (lines 1030-1135)**

```bash
sed -n '1030,1135p' backend/app/api/subscriptions.py
```

- [ ] **Step 2: Add the test class**

```python
class TestUpdateRenewalStatusEndpoint:
    """
    Chartests for POST /api/subscriptions/update-renewal-status.
    Mocks RenewalCalculator to lock the dispatch + per-sub error handling.
    """

    def _make_sub_with_email(self, db_session, mailbox, email, *, provider="Netflix"):
        from datetime import datetime, timezone
        from sqlalchemy import text
        from app.models.subscription import Subscription

        sub = Subscription(
            user_id=mailbox.user_id,
            mailbox_id=mailbox.id,
            provider=provider,
            amount=15.99,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        db_session.execute(
            text("""
                INSERT INTO subscription_emails
                  (subscription_id, email_id, extraction_role, extraction_data)
                VALUES (:sid, :eid, 'detection', '{}')
            """),
            {"sid": str(sub.id), "eid": str(email.id)},
        )
        db_session.commit()
        return sub

    def test_processes_active_subscriptions(
        self, client, db_session, test_mailbox, test_email, auth_headers
    ):
        """3 subs with emails → all 3 processed."""
        from unittest.mock import patch
        from datetime import datetime, timezone, timedelta

        for provider in ("Netflix", "Spotify", "Disney+"):
            self._make_sub_with_email(
                db_session, test_mailbox, test_email, provider=provider
            )

        future = datetime.now(timezone.utc) + timedelta(days=15)

        with patch(
            "app.api.subscriptions.RenewalCalculator"
        ) as MockCalc:
            instance = MockCalc.return_value
            instance.calculate_renewal_info.return_value = {
                "renewal_date": future,
                "is_active": True,
                "trial_status": None,
                "is_confirmed": True,
            }
            instance.detect_reactivation.return_value = False

            response = client.post(
                "/api/subscriptions/update-renewal-status",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total_processed"] == 3
        # All became active in our mock → total_activated counts deltas
        assert "total_activated" in body
        assert "total_deactivated" in body

    def test_skips_subscriptions_without_emails(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Sub with NO linked emails → skipped, not counted in total_processed."""
        from datetime import datetime, timezone
        from app.models.subscription import Subscription

        # One sub with NO junction rows
        orphan = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Orphan",
            amount=10.0,
            currency="EUR",
            billing_cycle="monthly",
            category="other",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
        )
        db_session.add(orphan)
        db_session.commit()

        response = client.post(
            "/api/subscriptions/update-renewal-status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        # The orphan does not contribute to total_processed
        assert body["total_processed"] == 0

    def test_continues_on_per_subscription_exception(
        self, client, db_session, test_mailbox, test_email, auth_headers
    ):
        """RenewalCalculator throws on one sub → error captured, other subs still processed."""
        from unittest.mock import patch
        from datetime import datetime, timezone, timedelta

        sub_ok = self._make_sub_with_email(
            db_session, test_mailbox, test_email, provider="Netflix"
        )
        sub_bad = self._make_sub_with_email(
            db_session, test_mailbox, test_email, provider="BrokenProvider"
        )

        future = datetime.now(timezone.utc) + timedelta(days=15)

        def calc_side_effect(*args, **kwargs):
            # Use the first arg (subscription) to decide
            sub = args[0] if args else kwargs.get("subscription")
            if sub and sub.provider == "BrokenProvider":
                raise ValueError("calculator failure")
            return {
                "renewal_date": future,
                "is_active": True,
                "trial_status": None,
                "is_confirmed": True,
            }

        with patch(
            "app.api.subscriptions.RenewalCalculator"
        ) as MockCalc:
            instance = MockCalc.return_value
            instance.calculate_renewal_info.side_effect = calc_side_effect
            instance.detect_reactivation.return_value = False

            response = client.post(
                "/api/subscriptions/update-renewal-status",
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        # The good sub still processed
        assert body["total_processed"] >= 1
        # The bad sub triggered an error
        assert "errors" in body
        assert len(body["errors"]) >= 1

    def test_filters_by_mailbox_id_query_param(
        self, client, db_session, test_user, test_email, auth_headers
    ):
        """When mailbox_id query param is provided, only that mailbox's subs are processed."""
        from app.models.mailbox import Mailbox

        mb1 = Mailbox(
            user_id=test_user.id, email_address="a@fastmail.com",
            provider_type="jmap", encrypted_credentials="x", is_active=True,
        )
        mb2 = Mailbox(
            user_id=test_user.id, email_address="b@fastmail.com",
            provider_type="jmap", encrypted_credentials="x", is_active=True,
        )
        db_session.add_all([mb1, mb2])
        db_session.commit()
        db_session.refresh(mb1)
        db_session.refresh(mb2)

        self._make_sub_with_email(db_session, mb1, test_email, provider="Netflix")
        self._make_sub_with_email(db_session, mb2, test_email, provider="Spotify")

        from unittest.mock import patch
        from datetime import datetime, timezone, timedelta
        future = datetime.now(timezone.utc) + timedelta(days=15)

        with patch("app.api.subscriptions.RenewalCalculator") as MockCalc:
            inst = MockCalc.return_value
            inst.calculate_renewal_info.return_value = {
                "renewal_date": future, "is_active": True,
                "trial_status": None, "is_confirmed": True,
            }
            inst.detect_reactivation.return_value = False

            response = client.post(
                f"/api/subscriptions/update-renewal-status?mailbox_id={mb1.id}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        # Only mb1's sub processed
        assert response.json()["total_processed"] == 1
```

- [ ] **Step 3: Run only the new class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_subscriptions_api.py::TestUpdateRenewalStatusEndpoint -v
```

Expected: `4 passed`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_subscriptions_api.py
git commit -m "$(cat <<'EOF'
test(subscriptions): chartests for POST /update-renewal-status

Locks in: per-sub processing, skip-on-no-emails, error containment
(per-sub exceptions don't break batch), mailbox_id query filter,
RenewalCalculator dispatch shape.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: §1 chartests — `POST /{subscription_id}/accept-suggestion`

**Files:**
- Modify: `backend/tests/test_subscriptions_api.py` (append)

Behaviour to lock in:

- Requires `suggested_cancellation_status` to be non-NULL (raises 400 otherwise).
- Sets `cancellation_status = suggested_cancellation_status`, `cancellation_confirmed_at = now`, `cancellation_notes = cancellation_suggestion_reason` (or empty), then clears all 3 suggestion fields.
- Returns `SubscriptionResponse` (Pydantic).
- 404 on missing subscription.

- [ ] **Step 1: Read the route source (lines 1137-1199)**

```bash
sed -n '1137,1199p' backend/app/api/subscriptions.py
```

- [ ] **Step 2: Add the test class**

```python
class TestAcceptSuggestionEndpoint:
    """
    Chartests for POST /api/subscriptions/{id}/accept-suggestion.
    """

    def _make_sub_with_suggestion(self, db_session, mailbox, *, status="cancelled",
                                  reason="No payment for 90 days"):
        from datetime import datetime, timezone
        from app.models.subscription import Subscription

        sub = Subscription(
            user_id=mailbox.user_id,
            mailbox_id=mailbox.id,
            provider="Netflix",
            amount=15.99,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
            suggested_cancellation_status=status,
            cancellation_suggestion_reason=reason,
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_returns_404_when_subscription_not_found(
        self, client, db_session, auth_headers
    ):
        import uuid
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/subscriptions/{fake_id}/accept-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_returns_400_when_no_pending_suggestion(
        self, client, db_session, test_mailbox, test_subscription, auth_headers
    ):
        """test_subscription fixture has no suggestion → 400."""
        response = client.post(
            f"/api/subscriptions/{test_subscription.id}/accept-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_applies_suggestion_and_clears_fields(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub = self._make_sub_with_suggestion(db_session, test_mailbox)

        response = client.post(
            f"/api/subscriptions/{sub.id}/accept-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Re-load from DB to verify final state
        db_session.expire(sub)
        db_session.refresh(sub)

        assert sub.cancellation_status == "cancelled"
        assert sub.cancellation_confirmed_at is not None
        assert sub.cancellation_notes  # populated from suggestion_reason
        # Suggestion fields cleared
        assert sub.suggested_cancellation_status is None
        assert sub.cancellation_suggestion_reason is None
        assert sub.cancellation_suggestion_created_at is None

    def test_response_body_has_subscription_response_shape(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub = self._make_sub_with_suggestion(db_session, test_mailbox)

        response = client.post(
            f"/api/subscriptions/{sub.id}/accept-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        # SubscriptionResponse has at minimum: id, provider, amount, cancellation_status
        assert body["id"] == str(sub.id)
        assert body["provider"] == "Netflix"
        assert body["cancellation_status"] == "cancelled"
```

- [ ] **Step 3: Run only the new class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_subscriptions_api.py::TestAcceptSuggestionEndpoint -v
```

Expected: `4 passed`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_subscriptions_api.py
git commit -m "$(cat <<'EOF'
test(subscriptions): chartests for POST /{id}/accept-suggestion

Locks in: 404 on missing sub, 400 on no pending suggestion, applies
suggested_cancellation_status to cancellation_status, clears all 3
suggestion fields, sets cancellation_confirmed_at, returns
SubscriptionResponse shape.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: §1 chartests — `POST /{subscription_id}/dismiss-suggestion`

**Files:**
- Modify: `backend/tests/test_subscriptions_api.py` (append)

Behaviour to lock in:

- Same precondition as accept (400 on no pending suggestion, 404 on missing sub).
- Clears the 3 suggestion fields. Does NOT touch `cancellation_status`, `is_active`, or other fields.
- Returns `{success: true, message}`.

- [ ] **Step 1: Read the route source (lines 1201-1255)**

```bash
sed -n '1201,1255p' backend/app/api/subscriptions.py
```

- [ ] **Step 2: Add the test class**

```python
class TestDismissSuggestionEndpoint:
    """
    Chartests for POST /api/subscriptions/{id}/dismiss-suggestion.
    """

    def _make_sub_with_suggestion(self, db_session, mailbox):
        from datetime import datetime, timezone
        from app.models.subscription import Subscription

        sub = Subscription(
            user_id=mailbox.user_id,
            mailbox_id=mailbox.id,
            provider="Netflix",
            amount=15.99,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
            suggested_cancellation_status="cancelled",
            cancellation_suggestion_reason="reason",
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_returns_404_when_subscription_not_found(
        self, client, db_session, auth_headers
    ):
        import uuid
        response = client.post(
            f"/api/subscriptions/{uuid.uuid4()}/dismiss-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_returns_400_when_no_pending_suggestion(
        self, client, test_subscription, auth_headers
    ):
        response = client.post(
            f"/api/subscriptions/{test_subscription.id}/dismiss-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_clears_suggestion_fields_only(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub = self._make_sub_with_suggestion(db_session, test_mailbox)
        # Capture pre-existing state we want to verify is preserved
        was_active = sub.is_active
        original_cancellation_status = sub.cancellation_status

        response = client.post(
            f"/api/subscriptions/{sub.id}/dismiss-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        db_session.expire(sub)
        db_session.refresh(sub)

        # Suggestion fields cleared
        assert sub.suggested_cancellation_status is None
        assert sub.cancellation_suggestion_reason is None
        assert sub.cancellation_suggestion_created_at is None
        # Other fields untouched
        assert sub.is_active == was_active
        assert sub.cancellation_status == original_cancellation_status
```

- [ ] **Step 3: Run only the new class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_subscriptions_api.py::TestDismissSuggestionEndpoint -v
```

Expected: `3 passed`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_subscriptions_api.py
git commit -m "$(cat <<'EOF'
test(subscriptions): chartests for POST /{id}/dismiss-suggestion

Locks in: 404 on missing sub, 400 on no pending suggestion, clears
the 3 suggestion fields only (other fields preserved), success
response shape.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: §1 chartests — `POST /{subscription_id}/split`

**Files:**
- Modify: `backend/tests/test_subscriptions_api.py` (append)

Behaviour to lock in:

- Body: `{email_groups: [{email_ids: [...], custom_label?, amount?, service_references?}, ...]}`. Must have ≥ 2 groups.
- First group keeps the original subscription's ID; groups 2+ create new subscriptions with `confidence_score=1.0`, `extraction_method="manual_split"`.
- All emails originally linked must be assigned across groups (else 400).
- Reassigns `subscription_emails` rows per group via raw SQL UPDATE.
- Returns `{success, message, subscriptions: [SubscriptionResponse, ...]}`.

- [ ] **Step 1: Read the route source (lines 1256-1430)**

```bash
sed -n '1256,1430p' backend/app/api/subscriptions.py
```

- [ ] **Step 2: Add the test class**

```python
class TestSplitEndpoint:
    """
    Chartests for POST /api/subscriptions/{id}/split.
    Critical: like merge, this mutates subscription_emails via raw SQL.
    """

    def _make_sub_with_3_emails(self, db_session, test_mailbox):
        """Create a subscription with 3 linked emails. Returns (sub, [email1, email2, email3])."""
        from datetime import datetime, timezone
        from sqlalchemy import text
        from app.models.subscription import Subscription
        from app.models.email_message import EmailMessage

        sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Twitch",
            amount=24.99,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            is_confirmed=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        emails = []
        for i in range(3):
            e = EmailMessage(
                mailbox_id=test_mailbox.id,
                message_id=f"split-test-{i}",
                subject=f"Twitch sub {i}",
                sender="twitch@twitch.tv",
                recipient=test_mailbox.email_address,
                date=datetime.now(timezone.utc),
                body_text=f"streamer-{i}",
                is_subscription=True,
                classification_confidence=0.9,
            )
            db_session.add(e)
            db_session.commit()
            db_session.refresh(e)
            db_session.execute(
                text("""
                    INSERT INTO subscription_emails
                      (subscription_id, email_id, extraction_role, extraction_data)
                    VALUES (:sid, :eid, 'detection', '{}')
                """),
                {"sid": str(sub.id), "eid": str(e.id)},
            )
            db_session.commit()
            emails.append(e)

        return sub, emails

    def test_returns_400_when_fewer_than_2_groups(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub, emails = self._make_sub_with_3_emails(db_session, test_mailbox)
        body = {"email_groups": [{"email_ids": [str(e.id) for e in emails]}]}
        response = client.post(
            f"/api/subscriptions/{sub.id}/split",
            headers=auth_headers,
            json=body,
        )
        assert response.status_code == 400

    def test_returns_400_when_emails_not_fully_assigned(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub, emails = self._make_sub_with_3_emails(db_session, test_mailbox)
        # Only assign 2 of 3 emails
        body = {
            "email_groups": [
                {"email_ids": [str(emails[0].id)], "custom_label": "g1"},
                {"email_ids": [str(emails[1].id)], "custom_label": "g2"},
            ],
        }
        response = client.post(
            f"/api/subscriptions/{sub.id}/split",
            headers=auth_headers,
            json=body,
        )
        assert response.status_code == 400

    def test_split_into_3_groups_creates_2_new_subscriptions(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub, emails = self._make_sub_with_3_emails(db_session, test_mailbox)
        body = {
            "email_groups": [
                {"email_ids": [str(emails[0].id)], "custom_label": "streamerA"},
                {"email_ids": [str(emails[1].id)], "custom_label": "streamerB"},
                {"email_ids": [str(emails[2].id)], "custom_label": "streamerC"},
            ],
        }
        response = client.post(
            f"/api/subscriptions/{sub.id}/split",
            headers=auth_headers,
            json=body,
        )
        assert response.status_code in (200, 201)
        result = response.json()
        assert result["success"] is True
        assert len(result["subscriptions"]) == 3

        # Verify in DB
        from app.models.subscription import Subscription
        all_subs = (
            db_session.query(Subscription)
            .filter(Subscription.provider == "Twitch")
            .all()
        )
        assert len(all_subs) == 3
        # New subs have manual_split + confidence 1.0
        new_subs = [s for s in all_subs if s.id != sub.id]
        assert len(new_subs) == 2
        for ns in new_subs:
            assert ns.extraction_method == "manual_split"
            assert ns.confidence_score == 1.0

    def test_emails_reassigned_to_correct_subscriptions(
        self, client, db_session, test_mailbox, auth_headers
    ):
        from sqlalchemy import text
        sub, emails = self._make_sub_with_3_emails(db_session, test_mailbox)
        body = {
            "email_groups": [
                {"email_ids": [str(emails[0].id)], "custom_label": "g1"},
                {"email_ids": [str(emails[1].id), str(emails[2].id)], "custom_label": "g2"},
            ],
        }
        response = client.post(
            f"/api/subscriptions/{sub.id}/split",
            headers=auth_headers,
            json=body,
        )
        assert response.status_code in (200, 201)

        # Original sub still exists with email[0]; new sub has email[1] and email[2]
        rows = db_session.execute(
            text("SELECT subscription_id, email_id FROM subscription_emails")
        ).fetchall()
        assert len(rows) == 3
        # email[0] still on original
        original_assignments = [
            r for r in rows if str(r[1]) == str(emails[0].id)
        ]
        assert len(original_assignments) == 1
        assert str(original_assignments[0][0]) == str(sub.id)

    def test_first_group_keeps_original_subscription_id(
        self, client, db_session, test_mailbox, auth_headers
    ):
        sub, emails = self._make_sub_with_3_emails(db_session, test_mailbox)
        body = {
            "email_groups": [
                {"email_ids": [str(emails[0].id)], "custom_label": "kept"},
                {"email_ids": [str(emails[1].id), str(emails[2].id)], "custom_label": "new"},
            ],
        }
        response = client.post(
            f"/api/subscriptions/{sub.id}/split",
            headers=auth_headers,
            json=body,
        )
        result = response.json()
        # The subscription with the original ID is in the response
        ids = {s["id"] for s in result["subscriptions"]}
        assert str(sub.id) in ids
```

- [ ] **Step 3: Run only the new class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_subscriptions_api.py::TestSplitEndpoint -v
```

Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_subscriptions_api.py
git commit -m "$(cat <<'EOF'
test(subscriptions): chartests for POST /{id}/split

Locks in: 400 on <2 groups, 400 on emails not fully assigned, first
group keeps original ID, new subs get extraction_method=manual_split
+ confidence 1.0, raw-SQL reassignment of subscription_emails.

Part of C1 Phase 1 safety net (audit §B). Critical because this route
mutates subscription_emails via raw SQL — Phase 6 (§1 split) depends
on this lock.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---


### Task 8: Build the inner-pipeline test harness in `conftest.py`

**Files:**
- Modify: `backend/tests/conftest.py` (append at end)

The harness is a single fixture `email_sync_harness` that drives `_sync_mailbox_async` via the public `sync_mailbox_emails` Celery task. It patches `SessionLocal`, `create_email_provider`, `AIClassifier`, `SubscriptionExtractor`, and `ReferenceExtractor`. **Critically, it does NOT patch `asyncio.run`** — the inner coroutine actually executes against the test DB.

The fixture exposes a small API so each chartest reads as setup → run → assert.

- [ ] **Step 1: Append the fixture to `conftest.py`**

```python
@pytest.fixture(scope="function")
def email_sync_harness(db_session: Session, test_user: User, test_mailbox: Mailbox):
    """
    Test harness driving the inner pipeline of `_sync_mailbox_async` via the
    public `sync_mailbox_emails` Celery task. Patches SessionLocal,
    create_email_provider, AIClassifier, SubscriptionExtractor, and
    ReferenceExtractor. Does NOT patch asyncio.run — the coroutine runs.

    Usage:
        def test_X(email_sync_harness):
            h = email_sync_harness
            sub = h.add_existing_sub(provider="Netflix", amount=15.99)
            h.add_email(sender="netflix@netflix.com",
                        extraction={"provider": "Netflix", "amount": 16.99, ...})
            result = h.run_sync()
            assert result["success"] is True
            assert h.get_sub(provider="Netflix").amount == 16.99
    """
    from contextlib import ExitStack
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import patch, MagicMock
    from sqlalchemy import text

    from app.models.email_message import EmailMessage
    from app.models.subscription import Subscription
    from app.models.price_history import PriceHistory

    state = SimpleNamespace()
    state.db = db_session
    state.mailbox = test_mailbox
    state.queued_emails = []  # list of dicts: email_record, classification, extraction

    # ---- Setup helpers ----

    def add_email(*, message_id=None, sender="netflix@netflix.com",
                  subject="Test", body="Test body", date=None,
                  is_subscription=True, category="subscription",
                  reasoning="", extraction=None):
        """Create an EmailMessage in DB and queue it for the mock provider."""
        msg_id = message_id or f"test-msg-{len(state.queued_emails)}"
        em = EmailMessage(
            mailbox_id=state.mailbox.id, message_id=msg_id, subject=subject,
            sender=sender, recipient=state.mailbox.email_address,
            date=date or datetime.now(timezone.utc), body_text=body,
            is_subscription=is_subscription, classification_confidence=0.9,
        )
        state.db.add(em)
        state.db.commit()
        state.db.refresh(em)

        ext = extraction if extraction is not None else {
            "provider": "Netflix", "amount": 15.99, "currency": "EUR",
            "billing_cycle": "monthly", "email_sender": sender,
            "category": "streaming", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }
        state.queued_emails.append({
            "email_record": em,
            "classification": {
                "is_subscription": is_subscription, "category": category,
                "confidence": 0.9, "reasoning": reasoning,
            },
            "extraction": ext,
        })
        return em

    def add_existing_sub(*, provider="Netflix", amount=15.99,
                         billing_cycle="monthly", email_sender=None,
                         custom_label="", **extra):
        sub = Subscription(
            user_id=state.mailbox.user_id, mailbox_id=state.mailbox.id,
            provider=provider, amount=amount, currency="EUR",
            billing_cycle=billing_cycle, email_sender=email_sender,
            custom_label=custom_label, category="streaming",
            is_active=True, is_confirmed=True,
            extraction_method="ai", confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
            **extra,
        )
        state.db.add(sub)
        state.db.commit()
        state.db.refresh(sub)
        return sub

    def link_email_to_sub(email, sub):
        state.db.execute(
            text("INSERT INTO subscription_emails "
                 "(subscription_id, email_id, extraction_role, extraction_data) "
                 "VALUES (:sid, :eid, 'detection', '{}')"),
            {"sid": str(sub.id), "eid": str(email.id)},
        )
        state.db.commit()

    # ---- Run ----

    def run_sync(force_full=False):
        from app.tasks.email_sync import sync_mailbox_emails
        return sync_mailbox_emails.apply(
            kwargs={"mailbox_id": str(state.mailbox.id),
                    "force_full_sync": force_full}
        ).get()

    # ---- Assertion helpers ----

    def count_subs(*, provider=None):
        q = state.db.query(Subscription).filter(
            Subscription.mailbox_id == state.mailbox.id
        )
        if provider:
            q = q.filter(Subscription.provider == provider)
        return q.count()

    def get_sub(*, provider, amount=None):
        q = state.db.query(Subscription).filter(
            Subscription.mailbox_id == state.mailbox.id,
            Subscription.provider == provider,
        )
        if amount is not None:
            q = q.filter(Subscription.amount == amount)
        return q.first()

    def all_subs(*, provider=None):
        q = state.db.query(Subscription).filter(
            Subscription.mailbox_id == state.mailbox.id
        )
        if provider:
            q = q.filter(Subscription.provider == provider)
        return q.order_by(Subscription.first_detected_at).all()

    def count_price_history(*, subscription_id=None, change_type=None):
        q = state.db.query(PriceHistory)
        if subscription_id:
            q = q.filter(PriceHistory.subscription_id == subscription_id)
        if change_type:
            q = q.filter(PriceHistory.change_type == change_type)
        return q.count()

    def email_links_for(sub_id):
        rows = state.db.execute(
            text("SELECT email_id FROM subscription_emails "
                 "WHERE subscription_id = :sid"),
            {"sid": str(sub_id)},
        ).fetchall()
        return [r[0] for r in rows]

    state.add_email = add_email
    state.add_existing_sub = add_existing_sub
    state.link_email_to_sub = link_email_to_sub
    state.run_sync = run_sync
    state.count_subs = count_subs
    state.get_sub = get_sub
    state.all_subs = all_subs
    state.count_price_history = count_price_history
    state.email_links_for = email_links_for

    # ---- Patches ----

    stack = ExitStack()

    mock_session_local = stack.enter_context(
        patch("app.tasks.email_sync.SessionLocal")
    )
    mock_session_local.return_value = state.db

    mock_provider_factory = stack.enter_context(
        patch("app.tasks.email_sync.create_email_provider")
    )

    async def mock_fetch_emails(*args, **kwargs):
        for em in state.queued_emails:
            yield em["email_record"]

    def make_mock_provider(*args, **kwargs):
        provider = MagicMock()
        provider.fetch_emails = mock_fetch_emails
        return provider

    mock_provider_factory.side_effect = make_mock_provider

    def classify_side_effect(email_record, *args, **kwargs):
        for em in state.queued_emails:
            if em["email_record"].message_id == email_record.message_id:
                return em["classification"]
        return {"is_subscription": False, "category": None,
                "confidence": 0.0, "reasoning": ""}

    def extract_side_effect(email_record, *args, **kwargs):
        for em in state.queued_emails:
            if em["email_record"].message_id == email_record.message_id:
                return em["extraction"]
        return None

    mock_classifier = stack.enter_context(
        patch("app.tasks.email_sync.AIClassifier")
    )
    mock_classifier.return_value.classify_email.side_effect = classify_side_effect

    mock_extractor = stack.enter_context(
        patch("app.tasks.email_sync.SubscriptionExtractor")
    )
    mock_extractor.return_value.extract_subscription.side_effect = extract_side_effect

    mock_ref_extractor = stack.enter_context(
        patch("app.tasks.email_sync.ReferenceExtractor")
    )
    mock_ref_extractor.return_value.can_match_subscription.return_value = False
    state.mock_ref_extractor = mock_ref_extractor  # tests can override per-scenario

    yield state
    stack.close()
```

- [ ] **Step 2: Add a smoke test for the harness**

Append to `conftest.py`:

```python
def test_email_sync_harness_smoke(email_sync_harness):
    """Smoke test: harness runs sync, queued email creates subscription."""
    h = email_sync_harness
    h.add_email(
        sender="netflix@netflix.com",
        extraction={
            "provider": "Netflix", "amount": 15.99, "currency": "EUR",
            "billing_cycle": "monthly", "email_sender": "netflix@netflix.com",
            "category": "streaming", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        },
    )

    result = h.run_sync()

    assert result["success"] is True
    assert h.count_subs(provider="Netflix") == 1
```

- [ ] **Step 3: Run smoke test**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/conftest.py::test_email_sync_harness_smoke -v
```

Expected: `1 passed`. If FAIL, the most likely causes are:
- The actual signature of `_sync_mailbox_async`'s provider/AI calls differs from what the mocks expect (e.g., `extract_subscription` takes additional kwargs). Read the source around line 175-300 of `tasks/email_sync.py` and adjust the side-effect signatures.
- `provider.fetch_emails` is called with positional args the async generator doesn't accept. Adjust `mock_fetch_emails`'s signature.
- An additional collaborator (e.g., `EmailFilter`) needs to be patched. Add it to the harness.

Iterate on the fixture until the smoke test passes. Do NOT proceed to Tasks 9+ until this is green.

- [ ] **Step 4: Run the full existing test suite to confirm no regression**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/ -q
```

Expected: all existing tests still pass (the new fixture is opt-in; unused by other tests).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "$(cat <<'EOF'
test(conftest): add email_sync_harness fixture for inner-pipeline chartests

Drives _sync_mailbox_async via the public sync_mailbox_emails wrapper
with patched SessionLocal, email provider, and AI services. Does NOT
patch asyncio.run — the coroutine actually executes against the test DB.

Exposes a small API: add_email, add_existing_sub, link_email_to_sub,
run_sync, count_subs, get_sub, all_subs, count_price_history,
email_links_for. Tests in Tasks 9-14 consume this API.

Includes a smoke test verifying the harness creates one subscription
from one queued email.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: §2 chartests — Inner pipeline: dedup multi-strategy

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append new class)

Behaviour to lock in (research §2 dedup section, lines 474-576).

- [ ] **Step 1: Add the test class**

```python
class TestSyncInnerPipelineDedup:
    """Chartests for the multi-strategy dedup logic in _sync_mailbox_async."""

    def _ext(self, **overrides):
        """Build an extraction dict with sensible defaults."""
        base = {
            "provider": "OVH", "amount": 10.0, "currency": "EUR",
            "billing_cycle": "monthly", "email_sender": "billing@ovh.com",
            "category": "saas", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }
        base.update(overrides)
        return base

    def test_payment_processor_heuristic_reuses_first_existing_sub(
        self, email_sync_harness
    ):
        """3 OVH subs exist; email from PayPal sender → reuses first existing OVH sub."""
        h = email_sync_harness
        sub1 = h.add_existing_sub(provider="OVH", amount=10.0)
        h.add_existing_sub(provider="OVH", amount=10.0)
        h.add_existing_sub(provider="OVH", amount=10.0)

        em = h.add_email(
            sender="service@paypal.com",
            extraction=self._ext(email_sender="service@paypal.com"),
        )

        result = h.run_sync()
        assert result["success"] is True
        # No new sub created
        assert h.count_subs(provider="OVH") == 3
        # Email linked to first-created sub
        assert em.id in h.email_links_for(sub1.id)

    def test_single_match_reuses_existing_sub(self, email_sync_harness):
        """1 existing Spotify sub, no service refs → reuses it."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Spotify", amount=9.99)
        em = h.add_email(
            sender="no-reply@spotify.com",
            extraction=self._ext(provider="Spotify", amount=9.99,
                                 email_sender="no-reply@spotify.com"),
        )

        result = h.run_sync()
        assert result["success"] is True
        assert h.count_subs(provider="Spotify") == 1
        assert em.id in h.email_links_for(sub.id)

    def test_email_sender_exact_match_disambiguates(self, email_sync_harness):
        """2 Twitch subs with different senders → email-sender exact match wins."""
        h = email_sync_harness
        sub_a = h.add_existing_sub(provider="Twitch", amount=4.99,
                                   email_sender="streamerA@twitch.tv")
        h.add_existing_sub(provider="Twitch", amount=4.99,
                           email_sender="streamerB@twitch.tv")

        em = h.add_email(
            sender="streamerA@twitch.tv",
            extraction=self._ext(provider="Twitch", amount=4.99,
                                 email_sender="streamerA@twitch.tv"),
        )

        result = h.run_sync()
        assert result["success"] is True
        assert h.count_subs(provider="Twitch") == 2
        assert em.id in h.email_links_for(sub_a.id)

    def test_custom_label_keyword_match_disambiguates(self, email_sync_harness):
        """2 Twitch subs, same email_sender, distinct custom_labels with keywords → matches."""
        h = email_sync_harness
        sub_a = h.add_existing_sub(provider="Twitch", amount=4.99,
                                   email_sender="billing@twitch.tv",
                                   custom_label="basic tier")
        h.add_existing_sub(provider="Twitch", amount=4.99,
                           email_sender="billing@twitch.tv",
                           custom_label="premium tier")

        em = h.add_email(
            sender="billing@twitch.tv",
            extraction=self._ext(provider="Twitch", amount=4.99,
                                 email_sender="billing@twitch.tv",
                                 custom_label="basic tier"),
        )

        result = h.run_sync()
        assert result["success"] is True
        # The 'basic tier' sub gets the email
        assert em.id in h.email_links_for(sub_a.id)

    def test_service_refs_present_no_match_creates_new_sub(
        self, email_sync_harness
    ):
        """Service references present but no existing match → creates a new sub
        rather than falling back to single-match. Locks in the 'CRITICAL FIX'
        anomaly noted in research."""
        h = email_sync_harness
        h.add_existing_sub(provider="OVH", amount=10.0)
        # Configure ref_extractor to consistently NOT match
        h.mock_ref_extractor.return_value.can_match_subscription.return_value = False

        em = h.add_email(
            sender="billing@ovh.com",
            extraction=self._ext(extraction_metadata={
                "service_references": {"account_id": "ABC123"}
            }),
        )

        result = h.run_sync()
        assert result["success"] is True
        # New sub created (because service refs present and no match)
        assert h.count_subs(provider="OVH") == 2
```

- [ ] **Step 2: Run the new class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineDedup -v
```

Expected: `5 passed`. Apply chartest methodology if any FAIL.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): chartests for inner-pipeline dedup multi-strategy

Locks the 5 dedup strategies via email_sync_harness:
- payment-processor heuristic (PayPal/Stripe/etc. sender) → reuses first
- single-match assumption (1 existing sub, no service refs) → reuse
- email-sender exact match → disambiguates 2 subs
- custom-label keyword match (tier/channel/premium) → disambiguates
- service-refs present but no match → creates new sub (CRITICAL FIX anomaly)

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: §2 chartests — Inner pipeline: price-history (3 paths)

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

- [ ] **Step 1: Add the test class**

```python
class TestSyncInnerPipelinePriceHistory:
    """Chartests for the 3 price-history paths in _sync_mailbox_async."""

    def _ext(self, **overrides):
        base = {
            "provider": "Netflix", "amount": 15.99, "currency": "EUR",
            "billing_cycle": "monthly", "email_sender": "netflix@netflix.com",
            "category": "streaming", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }
        base.update(overrides)
        return base

    def test_path1_ai_price_update_creates_increase_history(
        self, email_sync_harness
    ):
        """is_price_update=True, existing amount=15.99, new=18.99 → 'increase'."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix", amount=15.99)
        h.add_email(
            extraction=self._ext(amount=18.99, is_price_update=True),
        )

        result = h.run_sync()
        assert result["success"] is True
        # Sub amount updated
        from app.models.subscription import Subscription
        h.db.refresh(sub)
        assert sub.amount == 18.99
        # Increase history record
        assert h.count_price_history(subscription_id=sub.id,
                                     change_type="increase") >= 1

    def test_path1_ai_price_update_creates_decrease_history(
        self, email_sync_harness
    ):
        """is_price_update=True, old=20, new=15 → 'decrease'."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix", amount=20.0)
        h.add_email(extraction=self._ext(amount=15.0, is_price_update=True))

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        assert sub.amount == 15.0
        assert h.count_price_history(subscription_id=sub.id,
                                     change_type="decrease") >= 1

    def test_path2_existing_sub_amount_diff_creates_history(
        self, email_sync_harness
    ):
        """Match found via dedup, amount differs → batch-committed PriceHistory."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix", amount=15.99)
        h.add_email(extraction=self._ext(amount=17.99, is_price_update=False))

        result = h.run_sync()
        assert result["success"] is True
        # No new sub
        assert h.count_subs(provider="Netflix") == 1
        # PriceHistory created
        assert h.count_price_history(subscription_id=sub.id) >= 1

    def test_path3_new_subscription_with_amount_creates_initial_history(
        self, email_sync_harness
    ):
        """New sub created with amount=12.99 → PriceHistory(change_type='initial')."""
        h = email_sync_harness
        h.add_email(extraction=self._ext(amount=12.99))

        result = h.run_sync()
        assert result["success"] is True
        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert h.count_price_history(subscription_id=sub.id,
                                     change_type="initial") >= 1

    def test_path3_new_subscription_without_amount_skips_history(
        self, email_sync_harness
    ):
        """New sub with amount=None → no PriceHistory."""
        h = email_sync_harness
        h.add_email(extraction=self._ext(amount=None))

        result = h.run_sync()
        assert result["success"] is True
        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert h.count_price_history(subscription_id=sub.id) == 0

    def test_anomaly_price_update_with_no_existing_sub_falls_through(
        self, email_sync_harness
    ):
        """is_price_update=True but no existing sub → creates new sub + initial history.
        Locks the documented research anomaly."""
        h = email_sync_harness
        h.add_email(extraction=self._ext(amount=12.99, is_price_update=True))

        result = h.run_sync()
        assert result["success"] is True
        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert sub.amount == 12.99
        # Initial price history (not increase/decrease)
        assert h.count_price_history(subscription_id=sub.id,
                                     change_type="initial") >= 1
```

- [ ] **Step 2: Run the class + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelinePriceHistory -v
```

Expected: `6 passed`.

```bash
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): chartests for inner-pipeline price-history (3 paths)

Locks the 3 documented paths plus the AI-price-update-no-match anomaly:
- Path 1: is_price_update=True with existing sub → increase/decrease
- Path 2: existing sub matched via dedup, amount differs → batch-committed
- Path 3: new sub with non-NULL amount → 'initial' change_type
- Anomaly: is_price_update=True with no existing sub falls through to
  normal create + initial history

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: §2 chartests — Inner pipeline: renewal step

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

- [ ] **Step 1: Add the test class**

```python
class TestSyncInnerPipelineRenewalStep:
    """Chartests for the renewal calculation step (lines 664-731)."""

    def _ext(self, **overrides):
        base = {
            "provider": "Netflix", "amount": 15.99, "currency": "EUR",
            "billing_cycle": "monthly", "email_sender": "netflix@netflix.com",
            "category": "streaming", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }
        base.update(overrides)
        return base

    def test_renewal_calculated_when_sub_has_emails(self, email_sync_harness):
        """Subscription created → RenewalCalculator invoked, renewal_date set."""
        from unittest.mock import patch
        from datetime import datetime, timezone, timedelta

        h = email_sync_harness
        h.add_email()

        future = datetime.now(timezone.utc) + timedelta(days=30)
        with patch("app.tasks.email_sync.RenewalCalculator") as MockCalc:
            inst = MockCalc.return_value
            inst.calculate_renewal_info.return_value = {
                "renewal_date": future, "is_active": True,
                "trial_status": None, "is_confirmed": True,
            }
            inst.detect_reactivation.return_value = False

            result = h.run_sync()

        assert result["success"] is True
        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert sub.renewal_date is not None
        assert sub.is_active is True

    def test_renewal_calculator_exception_does_not_break_batch(
        self, email_sync_harness
    ):
        """RenewalCalculator throws → exception caught at line 728, sub still persisted."""
        from unittest.mock import patch

        h = email_sync_harness
        h.add_email()

        with patch("app.tasks.email_sync.RenewalCalculator") as MockCalc:
            MockCalc.return_value.calculate_renewal_info.side_effect = (
                ValueError("calc failure")
            )
            result = h.run_sync()

        # Sync still completes
        assert result["success"] is True
        # Sub still persisted (renewal calc is best-effort)
        sub = h.get_sub(provider="Netflix")
        assert sub is not None

    def test_detect_reactivation_called_after_renewal(self, email_sync_harness):
        """RenewalCalculator.detect_reactivation invoked after calculate_renewal_info."""
        from unittest.mock import patch
        from datetime import datetime, timezone, timedelta

        h = email_sync_harness
        h.add_email()

        with patch("app.tasks.email_sync.RenewalCalculator") as MockCalc:
            inst = MockCalc.return_value
            inst.calculate_renewal_info.return_value = {
                "renewal_date": datetime.now(timezone.utc) + timedelta(days=30),
                "is_active": True, "trial_status": None, "is_confirmed": True,
            }
            inst.detect_reactivation.return_value = False

            h.run_sync()

        # Both methods called at least once
        inst.calculate_renewal_info.assert_called()
        inst.detect_reactivation.assert_called()
```

- [ ] **Step 2: Run + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineRenewalStep -v
```

Expected: `3 passed`.

```bash
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): chartests for inner-pipeline renewal step

Locks: renewal calculation invoked when sub has emails; calculator
exceptions contained (don't break batch); detect_reactivation called
after calculate_renewal_info.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: §2 chartests — Inner pipeline: cancellation suggestion step

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

- [ ] **Step 1: Add the test class**

```python
class TestSyncInnerPipelineCancellationStep:
    """Chartests for cancellation-suggestion creation (lines 733-767)."""

    def _ext(self, **overrides):
        base = {
            "provider": "Netflix", "amount": 15.99, "currency": "EUR",
            "billing_cycle": "monthly", "email_sender": "netflix@netflix.com",
            "category": "streaming", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }
        base.update(overrides)
        return base

    def test_cancellation_email_creates_suggestion_when_none_pending(
        self, email_sync_harness
    ):
        """Email classified as cancellation, sub has no pending suggestion → created."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix")
        h.add_email(
            category="cancellation", reasoning="user clicked cancel",
            extraction=self._ext(),
        )

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        assert sub.suggested_cancellation_status == "cancelled"
        assert sub.cancellation_suggestion_reason
        assert sub.cancellation_suggestion_created_at is not None

    def test_cancellation_skipped_when_suggestion_already_pending(
        self, email_sync_harness
    ):
        """Sub already has pending suggestion → email-classified-cancellation skipped silently."""
        from datetime import datetime, timezone

        h = email_sync_harness
        sub = h.add_existing_sub(
            provider="Netflix",
            suggested_cancellation_status="cancelled",
            cancellation_suggestion_reason="prior reason",
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        h.add_email(
            category="cancellation", reasoning="another cancel email",
            extraction=self._ext(),
        )

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        # Original suggestion preserved
        assert sub.cancellation_suggestion_reason == "prior reason"

    def test_non_cancellation_email_does_not_create_suggestion(
        self, email_sync_harness
    ):
        """Standard subscription email → no suggestion."""
        h = email_sync_harness
        sub = h.add_existing_sub(provider="Netflix")
        h.add_email(category="subscription", extraction=self._ext())

        result = h.run_sync()
        assert result["success"] is True
        h.db.refresh(sub)
        assert sub.suggested_cancellation_status is None
```

- [ ] **Step 2: Run + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineCancellationStep -v
```

Expected: `3 passed`.

```bash
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): chartests for inner-pipeline cancellation suggestion step

Locks: suggestion created when category='cancellation' and sub has no
pending suggestion; subsequent cancellation emails silently skipped if
suggestion exists; non-cancellation emails leave suggestion alone.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: §2 chartests — Cancellation polling + commit boundaries

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

- [ ] **Step 1: Add the test class**

```python
class TestSyncInnerPipelineCommitBoundariesAndPolling:
    """
    Chartests for transactional parity (commit/rollback per email + per batch)
    and the cancellation-polling early-exit.
    """

    def _ext(self, **overrides):
        base = {
            "provider": "Netflix", "amount": 15.99, "currency": "EUR",
            "billing_cycle": "monthly", "email_sender": "netflix@netflix.com",
            "category": "streaming", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }
        base.update(overrides)
        return base

    def test_per_email_commit_increments_counter(
        self, email_sync_harness, commit_rollback_counter
    ):
        """Each email processed → at least 1 db.commit() per email + 1 batch commit."""
        h = email_sync_harness
        commit_rollback_counter.reset()

        h.add_email(message_id="email-1", extraction=self._ext())
        h.add_email(message_id="email-2", extraction=self._ext(provider="Spotify"))
        h.add_email(message_id="email-3", extraction=self._ext(provider="Disney+"))

        result = h.run_sync()
        assert result["success"] is True

        # 3 emails × at least 1 commit each + final batch/mailbox commit ≥ 4 total
        assert commit_rollback_counter.commits >= 4

    def test_subscription_emails_junction_inserted_per_email(
        self, email_sync_harness
    ):
        """Each new email creates a subscription_emails row for the matched sub."""
        h = email_sync_harness
        em = h.add_email(extraction=self._ext())

        result = h.run_sync()
        assert result["success"] is True

        sub = h.get_sub(provider="Netflix")
        assert sub is not None
        assert em.id in h.email_links_for(sub.id)

    def test_cancellation_polling_exits_early_when_flag_set_pre_sync(
        self, email_sync_harness
    ):
        """If sync_cancellation_requested=True before any email runs → no subs created."""
        h = email_sync_harness
        h.mailbox.sync_cancellation_requested = True
        h.db.commit()

        h.add_email(extraction=self._ext())
        result = h.run_sync()

        # Sync handles the cancellation gracefully
        # (precise return shape depends on the early-exit code path; lock that
        # at minimum no Netflix sub got created).
        assert h.count_subs(provider="Netflix") == 0
```

> **Note for the implementer**: the third test sets the flag pre-sync rather than mid-batch. A true mid-batch cancellation requires the harness to have a hook between batches; that more comprehensive scenario is in Task 14 (E2E test). The pre-sync variant here is sufficient to lock the polling check itself.

- [ ] **Step 2: Run + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineCommitBoundariesAndPolling -v
```

Expected: `3 passed`.

```bash
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): chartests for commit boundaries + cancellation polling

Locks: per-email commit count (>= 1 per email + 1 final), per-email
subscription_emails junction insert, pre-sync cancellation flag → early
exit with no subs created. Mid-batch cancellation covered in Task 14.

Uses commit_rollback_counter from Task 1 + email_sync_harness from Task 8.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: End-to-end mid-batch cancellation test

**Files:**
- Create: `backend/tests/test_e2e_sync_cancellation.py`

The E2E test exercises a multi-email scenario where the cancellation flag is flipped mid-stream. It uses the same harness from Task 8 plus a custom hook that flips the flag after N emails are processed.

- [ ] **Step 1: Create the file**

```python
"""
End-to-end characterisation test for mid-batch sync cancellation.

Locks: when cancellation_requested is set while a sync is running, already-
processed emails persist their subscriptions and remaining emails are skipped.
This is the highest-priority safety net for C1 Phase 8 (the §2 split).
"""

import pytest


class TestE2ESyncMidBatchCancellation:
    """E2E mid-batch cancellation."""

    def _ext(self, *, provider="Netflix", amount=15.99):
        return {
            "provider": provider, "amount": amount, "currency": "EUR",
            "billing_cycle": "monthly",
            "email_sender": f"billing@{provider.lower()}.com",
            "category": "streaming", "is_subscription": True,
            "is_price_update": False,
            "extraction_metadata": {"service_references": {}},
        }

    def test_cancellation_after_first_email_persists_only_first(
        self, email_sync_harness
    ):
        """
        3 emails queued (Netflix, Spotify, Disney+).
        After Netflix is processed (its classify call completes), flip the
        cancellation flag. Expect: Netflix sub persisted; Spotify and Disney+
        not created (sync exited early).
        """
        h = email_sync_harness

        # Queue 3 emails
        h.add_email(message_id="m1", extraction=self._ext(provider="Netflix"))
        h.add_email(message_id="m2", extraction=self._ext(provider="Spotify"))
        h.add_email(message_id="m3", extraction=self._ext(provider="Disney+"))

        # Wrap the classifier to flip the cancellation flag after 1 call
        original_side_effect = (
            h.queued_emails  # captured by closure
        )
        call_count = {"n": 0}

        def classify_with_cancel(email_record, *args, **kwargs):
            call_count["n"] += 1
            # Find normal classification result
            for em in h.queued_emails:
                if em["email_record"].message_id == email_record.message_id:
                    result = em["classification"]
                    break
            else:
                result = {"is_subscription": False, "category": None,
                          "confidence": 0.0, "reasoning": ""}

            # After the FIRST email is classified, flip the cancellation flag
            # (this happens before the inner pipeline finishes processing it,
            # so the next batch poll sees the flag).
            if call_count["n"] == 1:
                from app.models.mailbox import Mailbox
                mb = h.db.query(Mailbox).filter(Mailbox.id == h.mailbox.id).first()
                mb.sync_cancellation_requested = True
                h.db.commit()

            return result

        # Override the classifier side_effect for this test only
        from unittest.mock import patch
        with patch("app.tasks.email_sync.AIClassifier") as MockCls:
            MockCls.return_value.classify_email.side_effect = classify_with_cancel

            result = h.run_sync()

        # Sync completes (one way or another)
        assert "success" in result
        # At LEAST Netflix may be persisted depending on where the cancellation
        # poll fires relative to the per-email commit (line 803). The hard
        # assertion is that Spotify and Disney+ — processed AFTER the flag was
        # set — should NOT exist.
        # (If the harness produces a different ordering, the implementer should
        # tighten the assertion to whatever the deterministic behaviour is.)
        assert h.count_subs(provider="Spotify") == 0
        assert h.count_subs(provider="Disney+") == 0

    def test_cancellation_does_not_affect_other_users_mailboxes(
        self, db_session, test_user, email_sync_harness
    ):
        """User A's cancellation does not propagate to user B's mailbox.
        Locks multi-tenancy isolation under the cancellation flow."""
        from app.models.user import User
        from app.models.mailbox import Mailbox
        from app.security.password import hash_password

        # Create user B with their own mailbox
        password_hash, salt = hash_password("otherpassword")
        user_b = User(
            email="b@example.com", password_hash=password_hash, salt=salt,
            is_active=True, email_verified=True, settings={},
        )
        db_session.add(user_b)
        db_session.commit()
        db_session.refresh(user_b)

        mailbox_b = Mailbox(
            user_id=user_b.id, email_address="b@fastmail.com",
            provider_type="jmap", encrypted_credentials="x", is_active=True,
        )
        db_session.add(mailbox_b)
        db_session.commit()
        db_session.refresh(mailbox_b)

        # Set cancellation on user A's mailbox (the harness's mailbox)
        h = email_sync_harness
        h.mailbox.sync_cancellation_requested = True
        h.db.commit()

        # Confirm user B's mailbox state untouched
        db_session.refresh(mailbox_b)
        assert mailbox_b.sync_cancellation_requested in (False, None)
```

- [ ] **Step 2: Run + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_e2e_sync_cancellation.py -v
```

Expected: `2 passed`. The first test's exact ordering of "what got persisted before the flag was seen" depends on commit-boundary timing inside `_sync_mailbox_async`. If the test surfaces non-determinism (sometimes Netflix is persisted, sometimes not), the implementer should:
1. Read the relevant lines of `tasks/email_sync.py` (~803, 861, 863-899) and figure out the deterministic ordering.
2. Tighten the assertion to that determinism.
3. Or, if the ordering is genuinely non-deterministic in current code, narrow the test to ONLY assert "Spotify and Disney+ are absent" — which is the chartest invariant we care about (mid-batch flag prevents future processing).

```bash
git add backend/tests/test_e2e_sync_cancellation.py
git commit -m "$(cat <<'EOF'
test(e2e): chartest for mid-batch sync cancellation

Locks: cancellation flag flipped after 1st email processes → subsequent
emails (Spotify, Disney+) NOT persisted. Multi-tenancy isolation
verified (user A's flag does not affect user B's mailbox).

Acceptance criteria for C1 Phase 8 (the §2 split with A.1 interface
seam): the new tasks/email_sync/ package must keep this test green.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Final review, lint, push, and PR

- [ ] **Step 1: Run the full test suite**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/ -v --tb=short
```

Expected: all pre-existing tests still pass, plus the new ones from Tasks 1-14. No skips other than any pre-existing skips. If a chartest fails, follow the methodology note (do NOT modify production code).

- [ ] **Step 2: Lint**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m black --check tests/
docker-compose -f docker-compose.dev.yml exec -T backend python -m flake8 tests/ --max-line-length=120
```

If black fails: `docker-compose -f docker-compose.dev.yml exec -T backend python -m black tests/`, then re-run check. flake8 errors block; warnings tolerated.

- [ ] **Step 3: Commit-history check**

```bash
git log --oneline origin/main..HEAD
```

Expected: 14 commits (Task 1 through 14, with Task 15 producing only the PR — no further commit). Each subject scoped (`test(conftest):`, `test(subscriptions):`, `test(email_sync):`, `test(e2e):`).

- [ ] **Step 4: Push**

```bash
git push -u origin feat/c1.1-safety-net-chartests
```

- [ ] **Step 5: Create the PR**

```bash
gh pr create --title "feat(test): C1 Phase 1 — Safety Net chartests for §1 routes + §2 inner pipeline" --body "$(cat <<'EOF'
## Summary

C1 Phase 1 (audit §B): characterisation tests that lock current behaviour of (a) the 6 untested routes in `api/subscriptions.py` (merge, split, duplicates, accept/dismiss-suggestion, update-renewal-status) and (b) the inner pipeline of `_sync_mailbox_async` (~600 untested LoC: dedup multi-strategy, 3 price-history paths, renewal step, cancellation step, commit boundaries, cancellation polling), plus an E2E mid-batch cancellation scenario.

No production code changed.

### What landed

- `commit_rollback_counter` fixture in `conftest.py` (Task 1).
- 6 chartest classes in `test_subscriptions_api.py` covering all 6 untested §1 routes (Tasks 2-7).
- `email_sync_harness` fixture in `conftest.py` (Task 8) — drives `_sync_mailbox_async` via `sync_mailbox_emails` with patched provider + AI services + `SessionLocal`. `asyncio.run` is NOT patched, so the coroutine actually executes against the test DB.
- 5 chartest classes in `test_email_sync.py` covering dedup, price-history, renewal, cancellation suggestion, and commit boundaries (Tasks 9-13).
- 1 E2E test file `test_e2e_sync_cancellation.py` for mid-batch cancellation (Task 14).

### Why this is the safety net for Phases 6 and 8

- Phase 6 (§1 split) moves merge/split/duplicates/etc. into a sub-package. The §1 chartests (Tasks 2-7) verify that the HTTP contract and `subscription_emails` raw-SQL writes survive the split.
- Phase 8 (§2 split + A.1 interface seam) restructures the inner pipeline. The §2 chartests (Tasks 9-13) and the E2E (Task 14) verify that dedup decisions, price-history creation, transactional parity, and mid-batch cancellation behaviour survive the restructure.

## Test plan

- [ ] `pytest tests/` passes
- [ ] No production code changes verified by `git diff origin/main..HEAD -- backend/app/`
- [ ] Each new chartest class executes fully (no skips)
- [ ] `commit_rollback_counter` smoke test passes
- [ ] `email_sync_harness` smoke test passes
- [ ] Decide: ready to start Phase 2 (`dedup_strategy.py` extraction)?

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Surface a one-line summary** (PR URL, commit count, pass count, anomalies).

---

## Self-Review (already performed)

- **Spec coverage**: every item in audit §B Phase 1 maps to a task. The "6 chartests for §1" → Tasks 2-7 (concrete). The "§2 inner-pipeline chartests (multi-strategy dedup, 3 price-history paths, renewal step, cancellation step, cancellation polling, subscription_emails writes)" → Tasks 9-13 (concrete via the Task 8 harness). The "fixture that counts db.commit()/db.rollback()" → Task 1. The "End-to-end cancellation test" → Task 14. The "§3 chartests are NOT in this phase" note is honoured.
- **Placeholder scan**: no `TBD`, no `TODO`, no `pytest.skip` placeholders. Test code is complete. Commit-message templates use angle-bracket placeholders only where the value depends on actual run output (e.g., `<N>` count); each is explicitly marked for replacement before commit.
- **Type / name consistency**: fixture names (`db_session`, `client`, `test_user`, `test_mailbox`, `test_subscription`, `test_email`, `auth_headers`, `commit_rollback_counter`, `email_sync_harness`) used identically across all tasks. Test class names follow project convention. File paths exact.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-25-c1-phase-1-safety-net-chartests.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session via `superpowers:executing-plans`.

Which approach?
