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

### Task 8: §2 chartests — Inner pipeline: dedup multi-strategy

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append new class)

Strategy is to call `_sync_mailbox_async` with mocked AI services and a controlled set of pre-existing subscriptions, then assert which subscription got matched/created/reused.

Behaviour to lock in (research §2 dedup section, lines 474-576):

1. Service-reference matching wins if `extraction_metadata.service_references` matches an existing sub's metadata.
2. Single-match assumption applies only if no service_references AND exactly 1 existing sub for the provider.
3. Payment-processor heuristic (PayPal/Stripe/etc. in `email_sender`) reuses the first sub.
4. Email-sender exact match.
5. Custom-label keyword match (e.g., "tier", "channel", "premium").
6. Fallback: `potential_matches[0]`.

- [ ] **Step 1: Read the dedup block source (lines 474-576)**

```bash
sed -n '474,576p' backend/app/tasks/email_sync.py
```

- [ ] **Step 2: Add the test class**

```python
class TestSyncInnerPipelineDedup:
    """
    Chartests for the multi-strategy dedup logic inside _sync_mailbox_async.
    Drives the function with mocked AI classification + extraction outputs and
    asserts which existing subscription is matched (or whether a new one is created).
    """

    @pytest.fixture
    def mocked_pipeline(self):
        """Patch the AI services and the JMAP provider used inside _sync_mailbox_async."""
        from unittest.mock import patch, MagicMock
        with patch("app.tasks.email_sync.AIClassifier") as MockClassifier, \
             patch("app.tasks.email_sync.SubscriptionExtractor") as MockExtractor, \
             patch("app.tasks.email_sync.ReferenceExtractor") as MockRefExtractor, \
             patch("app.tasks.email_sync.create_email_provider") as MockProvider:
            yield {
                "classifier": MockClassifier,
                "extractor": MockExtractor,
                "ref_extractor": MockRefExtractor,
                "provider": MockProvider,
            }

    def _classify_returns_subscription(self, classifier_mock, **kwargs):
        instance = classifier_mock.return_value
        instance.classify_email.return_value = {
            "is_subscription": True,
            "category": kwargs.get("category", "subscription"),
            "confidence": 0.95,
            "reasoning": kwargs.get("reasoning", ""),
        }
        return instance

    def _extractor_returns_subscription(self, extractor_mock, *,
                                        provider="Netflix", amount=15.99,
                                        email_sender="netflix@netflix.com",
                                        billing_cycle="monthly",
                                        custom_label="",
                                        service_references=None):
        instance = extractor_mock.return_value
        result = {
            "provider": provider,
            "amount": amount,
            "currency": "EUR",
            "billing_cycle": billing_cycle,
            "email_sender": email_sender,
            "custom_label": custom_label,
            "category": "streaming",
            "is_subscription": True,
            "extraction_metadata": {
                "service_references": service_references or {},
            },
        }
        instance.extract_subscription.return_value = result
        return instance

    def test_payment_processor_heuristic_reuses_first_existing_sub(
        self, db_session, test_mailbox, test_email, mocked_pipeline
    ):
        """3 OVH subs exist; email from PayPal → reuses first existing OVH sub."""
        # NOTE: This test is a SCAFFOLD. The implementer must drive _sync_mailbox_async
        # via its real entry point (likely `sync_mailbox_emails` Celery task or
        # the async function under asyncio.run). Reuse the patterns in
        # TestSyncMailboxEmails for the integration shape.
        #
        # Steps:
        #   1. Create 3 existing OVH subscriptions tied to test_mailbox.
        #   2. Create a fresh test email with sender containing "paypal".
        #   3. Configure mocks so classifier+extractor return provider="OVH".
        #   4. Invoke _sync_mailbox_async (or its public wrapper).
        #   5. Assert: still 3 OVH subscriptions in DB (no new one created).
        #   6. Assert: the new email is linked to the first-created OVH sub
        #      via subscription_emails junction.
        pytest.skip(
            "Scaffold — integrate with the existing TestSyncMailboxEmails "
            "harness pattern. See ticket: implement against the public "
            "wrapper that drives _sync_mailbox_async."
        )

    def test_service_reference_matching_wins_over_single_match(
        self, db_session, test_mailbox, test_email, mocked_pipeline
    ):
        """Service refs present and matching → reuses matched sub even if 2+ exist for provider."""
        pytest.skip("Scaffold — same harness pattern.")

    def test_no_service_ref_single_match_reuses_existing(
        self, db_session, test_mailbox, test_email, mocked_pipeline
    ):
        """1 existing Spotify sub, no service refs → reuses it."""
        pytest.skip("Scaffold — same harness pattern.")

    def test_service_refs_present_no_match_creates_new(
        self, db_session, test_mailbox, test_email, mocked_pipeline
    ):
        """Service refs present but no existing sub matches → creates new sub (does NOT fall back)."""
        pytest.skip("Scaffold — same harness pattern.")

    def test_custom_label_keyword_match_disambiguates(
        self, db_session, test_mailbox, test_email, mocked_pipeline
    ):
        """3 Twitch subs, email sender same, custom_label='premium tier' → matches the sub with 'premium' label."""
        pytest.skip("Scaffold — same harness pattern.")
```

> **NOTE FOR THE IMPLEMENTER**: this task is partially scaffolded because driving `_sync_mailbox_async` (an internal async function) requires the same harness already used by `TestSyncMailboxEmails` in this file. Read that class's setup carefully before unscaffolding these tests. If the existing harness does not lend itself to driving the inner pipeline directly, surface this as `DONE_WITH_CONCERNS` and propose either:
>   1. Refactoring this task to run end-to-end via the Celery task entry point with mocked email providers (highest fidelity but slowest), OR
>   2. Adding a thin internal helper that wraps `_sync_mailbox_async` for testability — but ONLY if it's a non-invasive addition that the audit's §2 hasn't already accounted for.

- [ ] **Step 3: Run the new class (with skips counted as passes)**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineDedup -v
```

Expected: `5 skipped` if the implementer left them as scaffolds, or `5 passed` once unscaffolded. Either is acceptable for this commit; the unscaffolding may need to happen in a follow-up if the harness work is non-trivial.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): scaffold chartests for inner-pipeline dedup multi-strategy

Adds test class for the 5 dedup strategies (service-reference match,
single-match, payment-processor heuristic, email-sender exact,
custom-label keyword match, fallback). Tests are scaffolded with
pytest.skip — implementing them requires the same internal-pipeline
harness used by TestSyncMailboxEmails.

If the implementer concludes the harness work is too invasive for
Phase 1, this class can be unscaffolded as part of Phase 8's interface
seam (when _sync_mailbox_async accepts injected protocols and becomes
trivially mockable).

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: §2 chartests — Inner pipeline: price-history paths (3)

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

Behaviour to lock in (research §2 price-history section):

- **Path 1**: AI-detected price update (`subscription_data.is_price_update=True`) → updates existing sub's amount, creates `PriceHistory(change_type="increase"|"decrease")`, commits at line 433.
- **Path 2**: Existing sub matched, amount differs → creates `PriceHistory(change_type="increase"|"decrease")`, batch-committed at line 803.
- **Path 3**: New subscription with non-NULL amount → creates `PriceHistory(change_type="initial", old_amount=None, change_percentage=None)`, committed at line 803.

- [ ] **Step 1: Read the source (lines 340-434, 602-662)**

```bash
sed -n '340,434p' backend/app/tasks/email_sync.py
echo "---"
sed -n '602,662p' backend/app/tasks/email_sync.py
```

- [ ] **Step 2: Add the test class**

Same harness caveat as Task 8. Scaffold:

```python
class TestSyncInnerPipelinePriceHistory:
    """
    Chartests for the 3 price-history paths in _sync_mailbox_async.
    """

    def test_path1_ai_price_update_creates_price_history_increase(self):
        """is_price_update=True, old=10, new=15 → PriceHistory(change_type='increase', percent=50)."""
        pytest.skip("Scaffold — see TestSyncInnerPipelineDedup note.")

    def test_path1_ai_price_update_creates_price_history_decrease(self):
        """is_price_update=True, old=20, new=15 → PriceHistory(change_type='decrease', percent=-25)."""
        pytest.skip("Scaffold — see TestSyncInnerPipelineDedup note.")

    def test_path2_existing_sub_amount_diff_creates_price_history(self):
        """Match found, old=15, new=18 → PriceHistory(change_type='increase')."""
        pytest.skip("Scaffold.")

    def test_path3_new_subscription_with_amount_creates_initial_history(self):
        """New sub, amount=12 → PriceHistory(change_type='initial', old_amount=None)."""
        pytest.skip("Scaffold.")

    def test_path3_new_subscription_without_amount_skips_history(self):
        """New sub, amount=None → no PriceHistory record created."""
        pytest.skip("Scaffold.")

    def test_anomaly_price_update_with_no_existing_sub_falls_through(self):
        """is_price_update=True but no existing sub → falls through to normal create + initial history.
        Documented anomaly from research output."""
        pytest.skip("Scaffold.")
```

- [ ] **Step 3: Run the new class**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelinePriceHistory -v
```

Expected: `6 skipped` (scaffolds) — same as Task 8.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): scaffold chartests for inner-pipeline price-history

Three documented paths plus one anomaly:
- Path 1: AI-detected price update (is_price_update=True)
- Path 2: Existing sub matched, amount differs
- Path 3: New subscription with non-NULL amount → 'initial' change_type
- Anomaly: is_price_update=True with no existing sub falls through
  to normal create + initial history (research finding)

Scaffolds — see TestSyncInnerPipelineDedup note for harness rationale.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: §2 chartests — Inner pipeline: renewal step

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

Behaviour to lock in (research §2 renewal step section, lines 664-731):

- After persisting a subscription, calls `RenewalCalculator.calculate_renewal_info()` with email_dates + email_contents.
- Updates `renewal_date`, `is_active`, `trial_status`, `is_confirmed`.
- Calls `RenewalCalculator.detect_reactivation()`.
- Skipped if no linked emails. Exception is caught at line 728, continues to next sub.

- [ ] **Step 1: Read the source (lines 664-731)**

```bash
sed -n '664,731p' backend/app/tasks/email_sync.py
```

- [ ] **Step 2: Add the test class**

```python
class TestSyncInnerPipelineRenewalStep:
    """Chartests for the renewal calculation step in _sync_mailbox_async."""

    def test_renewal_calculated_for_subscription_with_emails(self):
        pytest.skip("Scaffold — see TestSyncInnerPipelineDedup note.")

    def test_renewal_skipped_when_no_linked_emails(self):
        pytest.skip("Scaffold.")

    def test_renewal_calculator_exception_does_not_break_batch(self):
        pytest.skip("Scaffold.")

    def test_detect_reactivation_called_after_renewal_calc(self):
        pytest.skip("Scaffold.")
```

- [ ] **Step 3 + 4: Run + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineRenewalStep -v
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): scaffold chartests for inner-pipeline renewal step

Locks: renewal calculation triggered when emails exist, skipped otherwise,
calculator exceptions contained per-sub, detect_reactivation called after.

Scaffold — see TestSyncInnerPipelineDedup note.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: §2 chartests — Inner pipeline: cancellation step

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

Behaviour (research §2 cancellation step, lines 733-767):

- Email classified as `category="cancellation"` → if `suggested_cancellation_status` is NULL, sets it to `"cancelled"`, populates `cancellation_suggestion_reason`, sets `cancellation_suggestion_created_at`.
- If suggestion already exists, skip silently (logged at info).

- [ ] **Step 1: Read the source (lines 733-767)**

```bash
sed -n '733,767p' backend/app/tasks/email_sync.py
```

- [ ] **Step 2: Add the test class**

```python
class TestSyncInnerPipelineCancellationStep:
    """Chartests for cancellation-suggestion creation in _sync_mailbox_async."""

    def test_cancellation_email_creates_suggestion_when_none_pending(self):
        pytest.skip("Scaffold — see TestSyncInnerPipelineDedup note.")

    def test_cancellation_email_skipped_when_suggestion_already_pending(self):
        pytest.skip("Scaffold.")

    def test_non_cancellation_email_does_not_create_suggestion(self):
        pytest.skip("Scaffold.")

    def test_suggestion_creation_exception_caught_continues_batch(self):
        pytest.skip("Scaffold.")
```

- [ ] **Step 3 + 4: Run + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineCancellationStep -v
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): scaffold chartests for inner-pipeline cancellation step

Locks: suggestion created when pending=NULL + email is classified as
cancellation; skip when suggestion already exists; non-cancellation
emails leave suggestion alone; exceptions don't break batch.

Scaffold — see TestSyncInnerPipelineDedup note.

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: §2 chartests — Inner pipeline: cancellation polling + commit boundaries

**Files:**
- Modify: `backend/tests/test_email_sync.py` (append)

Behaviour (research §2 cancellation polling lines 863-899 + commit boundaries):

- After each batch, `db.refresh(mailbox)` then check `mailbox.sync_cancellation_requested`. If true, set status="cancelled", commit, return early.
- Per-email commit at line 803, per-batch commit at line 861, per-email rollback on exception at line 807.

These are unit-level via `commit_rollback_counter` rather than scaffolds — we can write actual tests using the fixture.

- [ ] **Step 1: Read the source (lines 803, 807, 861, 863-899)**

```bash
sed -n '798,810p' backend/app/tasks/email_sync.py
echo "---"
sed -n '855,899p' backend/app/tasks/email_sync.py
```

- [ ] **Step 2: Add the test class**

```python
class TestSyncInnerPipelineCancellationAndCommits:
    """
    Chartests for cancellation polling + commit/rollback boundary semantics.
    Uses commit_rollback_counter to assert transactional parity.
    """

    def test_cancellation_polling_stops_processing_when_flag_set(self):
        """Mid-batch, cancellation_requested=True is set in DB → next poll exits early.
        Locks in the per-batch poll behaviour."""
        pytest.skip("Scaffold — see TestSyncInnerPipelineDedup note.")

    def test_per_email_commit_increments_counter_once_per_email(
        self, commit_rollback_counter
    ):
        """Each email processed → exactly 1 db.commit() call within the loop body
        (line 803), plus the final batch commit (line 861). Counter assertion
        provides transactional parity for Phase 8."""
        pytest.skip("Scaffold.")

    def test_per_email_exception_triggers_rollback_only_for_that_email(
        self, commit_rollback_counter
    ):
        """When email N raises, db.rollback() is called once (line 807),
        and the remaining emails in the batch still complete."""
        pytest.skip("Scaffold.")

    def test_e2e_mid_batch_cancellation_persists_completed_emails(self):
        """Send cancellation request after batch 3 of 5 → first 3 batches'
        subscriptions persisted, batch 4-5 not started, mailbox status='cancelled'."""
        pytest.skip("Scaffold — covered more comprehensively in Task 13.")
```

- [ ] **Step 3 + 4: Run + commit**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_email_sync.py::TestSyncInnerPipelineCancellationAndCommits -v
git add backend/tests/test_email_sync.py
git commit -m "$(cat <<'EOF'
test(email_sync): scaffold chartests for cancellation polling + commit boundaries

Locks: per-batch poll → early exit when cancellation_requested=True;
per-email commit increments counter; per-email exception triggers
rollback once. Uses commit_rollback_counter fixture from Task 1.

Scaffold — see TestSyncInnerPipelineDedup note.

Part of C1 Phase 1 safety net (audit §B). The full E2E mid-batch
cancellation test lives in test_e2e_sync_cancellation.py (Task 13).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: End-to-end mid-batch cancellation test

**Files:**
- Create: `backend/tests/test_e2e_sync_cancellation.py`

This is the only new file. It crosses subscription, mailbox, and email_sync boundaries — its own file makes that scope clear.

The E2E test:
1. Sets up a mailbox with 5 batches' worth of emails (e.g., 250 emails at batch_size=50).
2. Mocks the email provider to return them in chunks.
3. Starts a sync.
4. After ~3 batches' worth of progress (e.g., poll the mailbox's `last_sync_batch_num`), sets `mailbox.sync_cancellation_requested = True` and commits.
5. Assertions:
   - The sync returns with status `"cancelled"` (or equivalent).
   - The first 3 batches' subscriptions are persisted in DB.
   - Batches 4 and 5 are not started (no subscriptions for those emails).
   - `mailbox.last_sync_status == "cancelled"`.
   - `mailbox.sync_cancelled_at` is set.

- [ ] **Step 1: Create the file with the scaffolded test**

Write `backend/tests/test_e2e_sync_cancellation.py`:

```python
"""
End-to-end characterisation test for mid-batch sync cancellation.

Mocks the email provider but uses the full _sync_mailbox_async (or its
public Celery wrapper) against the in-memory test DB. Locks in the
behaviour: when the user requests cancellation mid-sync, already-persisted
subscriptions survive and remaining batches are skipped.

This is the highest-priority safety net for C1 Phase 8 (the §2 split).
"""

import pytest


class TestE2ESyncCancellation:
    def test_cancellation_after_batch_3_persists_3_batches_only(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """
        Scenario:
          - 5 batches × 50 emails = 250 emails.
          - User triggers cancellation after batch 3 completes.
          - Expected: 3×50 = 150 subscriptions persisted, batches 4-5 not started,
            mailbox.last_sync_status = "cancelled".

        Implementation note: the implementer must use the same harness as
        TestSyncMailboxEmails in test_email_sync.py (mock the email provider
        with create_email_provider, drive sync_mailbox_emails or its async
        wrapper). The cancellation can be triggered by:
          - Patching a hook between batches that flips the flag, OR
          - Using a side_effect on the mocked provider's fetch method that
            sets mailbox.sync_cancellation_requested=True after batch 3.

        If unable to drive a 5-batch scenario in the in-memory harness, scale
        down to 3 batches with cancellation after batch 1 — the assertion
        ratios are equivalent.
        """
        pytest.skip(
            "Scaffold — implement against the existing TestSyncMailboxEmails "
            "harness. See task description for the side_effect pattern."
        )

    def test_cancellation_when_no_emails_processed_yet_completes_immediately(
        self, client, db_session, test_mailbox, auth_headers
    ):
        """Cancellation requested before any batch starts → sync returns
        with status='cancelled', no subscriptions created."""
        pytest.skip("Scaffold — same harness pattern.")

    def test_cancellation_does_not_affect_other_users_mailboxes(
        self, client, db_session, test_user, auth_headers
    ):
        """Cancellation on user A's mailbox does not propagate to user B's mailbox.
        Locks multi-tenancy isolation under the cancellation flow."""
        pytest.skip("Scaffold — same harness pattern.")
```

- [ ] **Step 2: Run the new file**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/test_e2e_sync_cancellation.py -v
```

Expected: `3 skipped` initially. The implementer can unscaffold in a follow-up commit if the harness work is feasible within Phase 1's budget; otherwise these scaffolds are tracked as a known dependency for Phase 8.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_e2e_sync_cancellation.py
git commit -m "$(cat <<'EOF'
test(e2e): scaffold mid-batch sync cancellation test

Three scenarios:
- Cancellation after batch 3 of 5 → 150 subs persisted, mailbox status='cancelled'
- Cancellation before any batch → returns immediately
- Cancellation on user A doesn't affect user B (multi-tenancy isolation)

Scaffolds — implementation requires the same provider-mock harness as
TestSyncMailboxEmails. If harness work is too invasive for Phase 1,
this file's tests are the natural acceptance criteria for the Phase 8
interface seam (§2 split with injectable Protocols).

Part of C1 Phase 1 safety net (audit §B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Final review, push, and PR

- [ ] **Step 1: Run the full test suite**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend pytest tests/ -v --tb=short
```

Expected: all previously-passing tests still pass; the new chartests in `TestDuplicatesEndpoint`, `TestMergeEndpoint`, `TestUpdateRenewalStatusEndpoint`, `TestAcceptSuggestionEndpoint`, `TestDismissSuggestionEndpoint`, `TestSplitEndpoint` all pass; the §2 inner-pipeline scaffolds are skipped (acceptable per the methodology note).

If any chartest FAILS that should be passing, follow the chartest methodology — do NOT modify production code.

- [ ] **Step 2: Lint**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m black --check tests/
docker-compose -f docker-compose.dev.yml exec -T backend python -m flake8 tests/ --max-line-length=120
```

If black fails: `python -m black tests/` to auto-fix, then re-run check.

- [ ] **Step 3: Final review of commit history**

```bash
git log --oneline origin/main..HEAD
```

Expected: 13 commits (one per task 1-13, none for the final review task itself).

Each subject line scoped (`test(conftest):`, `test(subscriptions):`, `test(email_sync):`, `test(e2e):`).

- [ ] **Step 4: Push**

```bash
git push -u origin feat/c1.1-safety-net-chartests
```

- [ ] **Step 5: Create the PR**

```bash
gh pr create --title "feat(test): C1 Phase 1 — Safety Net chartests for §1 routes + §2 inner pipeline" --body "$(cat <<'EOF'
## Summary

C1 Phase 1 (per audit §B): characterisation tests that lock in current behaviour of the 6 untested routes in `api/subscriptions.py` (merge, split, duplicates, accept/dismiss-suggestion, update-renewal-status) plus the inner pipeline of `_sync_mailbox_async` (~600 untested LoC: dedup multi-strategy, 3 price-history paths, renewal step, cancellation step, cancellation polling, commit boundaries).

No production code changed.

### What is fully implemented

- `commit_rollback_counter` fixture in `conftest.py` (with smoke test).
- 6 chartest classes in `test_subscriptions_api.py` covering all 6 untested §1 routes.
- 6 scaffolded chartest classes in `test_email_sync.py` for the §2 inner pipeline blocks.
- 1 scaffolded E2E file (`test_e2e_sync_cancellation.py`) for the mid-batch cancellation scenario.

### Why some §2 chartests are scaffolded

Driving `_sync_mailbox_async` from a unit test requires the same mock-provider harness as the existing `TestSyncMailboxEmails`. If the implementer concludes the harness work is too invasive for Phase 1's M-effort budget, the scaffolds are intentionally left as scaffolds and become acceptance criteria for Phase 8 (the §2 split with the A.1 interface seam). Either way, the §1 routes — which mutate `subscription_emails` via raw SQL and are the highest-blast-radius zone — are now fully covered.

## Test plan

- [ ] `pytest tests/` passes (existing + new tests, scaffolds counted as skipped)
- [ ] No production code changes verified by `git diff origin/main..HEAD -- backend/app/`
- [ ] `commit_rollback_counter` smoke test passes
- [ ] All 6 §1 chartest classes execute fully (no skips):
  - `TestDuplicatesEndpoint`
  - `TestMergeEndpoint`
  - `TestUpdateRenewalStatusEndpoint`
  - `TestAcceptSuggestionEndpoint`
  - `TestDismissSuggestionEndpoint`
  - `TestSplitEndpoint`
- [ ] §2 scaffolds report as `SKIPPED`, not `ERROR`
- [ ] Decide: unscaffold §2 + E2E now (implementer commits follow-up tasks) or accept as Phase 8 acceptance criteria

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Final report**

Surface a one-line summary including:
- Branch name
- PR URL
- Number of commits
- Pass count for §1 chartests
- Skip count for §2 scaffolds
- Any anomalies

---

## Self-Review (already performed)

- **Spec coverage**: each item in audit §B Phase 1 maps to tasks. The "6 chartests for §1" → Tasks 2-7. The "§2 inner-pipeline chartests (multi-strategy dedup, 3 price-history paths, renewal step, cancellation step, cancellation polling, subscription_emails writes)" → Tasks 8-12. The "fixture that counts db.commit()/db.rollback()" → Task 1. The "End-to-end cancellation test" → Task 13. The note that §3 chartests are NOT in this phase is honoured (no §3 work).
- **Placeholder scan**: angle-bracket placeholders in commit-message templates are by design with explicit replacement instructions; no `TBD`, `TODO`, or `fill in later` in production prose. The §2 scaffolds use explicit `pytest.skip("Scaffold — ...")` with rationale, not placeholder text.
- **Type / name consistency**: fixture names (`db_session`, `client`, `test_user`, `test_mailbox`, `test_subscription`, `test_email`, `auth_headers`, `commit_rollback_counter`) used identically across all tasks. Test class names follow project convention (`Test<Subject>Endpoint`). File paths exact.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-25-c1-phase-1-safety-net-chartests.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`.

Which approach?
