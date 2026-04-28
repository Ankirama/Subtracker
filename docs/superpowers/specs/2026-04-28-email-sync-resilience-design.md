# Email Sync Resilience & Error Tracking — Design

**Status:** Draft (pending user review)
**Date:** 2026-04-28
**Owner:** ankirama

---

## 1. Context

The email sync pipeline (`backend/app/tasks/email_sync/`) currently fails the entire batch when a single email cannot be persisted. This was triggered in production by a single Gmail auto-reply whose `subject` exceeded `email_messages.subject` (`varchar(500)`), raising `psycopg2.errors.StringDataRightTruncation`. The transaction rolled back, SQLAlchemy entered `PendingRollbackError`, Celery retried the same poisoned message twice, gave up, and left the mailbox row in `last_sync_status='in_progress'` with `progress_percentage=50` — a zombie state from the user's point of view.

Three independent defects compounded:

1. **Schema too narrow.** `subject`, `sender_name`, `message_id`, `thread_id` are `varchar(500)` or `varchar(255)`. RFC 5322 places no hard limit on subjects; provider-generated tokens routinely exceed 500 bytes.
2. **No per-email isolation.** A single failure invalidates the SQLAlchemy session for the whole batch.
3. **No zombie recovery.** A crashed task does not transition `mailbox.last_sync_status` to `failed`.

The fix targets all three, plus introduces a first-class persistence + UI surface for sync errors so users and the admin can see, retry, or dismiss skipped emails.

## 2. Goals

- A single malformed email never aborts a sync batch.
- Every skipped email leaves a structured, queryable record with enough context to retry or debug it.
- The mailbox owner sees their skipped emails on their mailbox view, with retry / ignore actions.
- The admin sees skipped emails cross-mailbox with full diagnostic detail.
- A circuit breaker prevents pathological loops where every email fails for a system-wide reason.
- Schema is widened so the most common cause of failure (oversized headers) is removed at its source.

## 3. Non-goals

- Push-notification delivery for sync errors. In-app notifications only.
- Periodic background retry. Retry is user- or admin-triggered.
- Backfilling `email_sync_errors` rows for historical skips that happened before this feature.
- Encryption-at-rest of `raw_payload`. JSONB stays in clear; revisit if PII becomes a concern.
- Refactors of code outside the email sync save path or the new admin/mailbox views.
- Mobile-specific UI optimisation for the new pages.
- Cleanup items in audit §C (`docs/superpowers/audits/2026-04-25-backend-architecture-audit.md`).

## 4. Architecture

The save loop inside the email sync pipeline is wrapped at the per-email level:

```
for email in batch:
    try:
        process_single_email(...)            # classify + extract + dedup + persist
        consecutive_unexpected = 0
    except Exception as exc:
        error_type = classify_exception(exc)
        record_sync_error(...)               # persist email_sync_errors row + log
        db.rollback()                        # restore session
        if error_type == "unexpected":
            consecutive_unexpected += 1
            if consecutive_unexpected >= 5:
                trip_circuit_breaker(...)    # mark mailbox failed, raise
                raise SyncCircuitBreakerError(...)
        continue                             # next email, batch survives
```

The mailbox sync wrapper transitions `last_sync_status` to `failed` in a `finally` / Celery `on_failure` handler, fixing the zombie state.

## 5. Database changes

One Alembic migration. Description: `widen_email_messages_text_columns_and_add_email_sync_errors`.

### 5.1 Schema fix on `email_messages`

```sql
ALTER TABLE email_messages ALTER COLUMN subject     TYPE TEXT;
ALTER TABLE email_messages ALTER COLUMN sender_name TYPE TEXT;
ALTER TABLE email_messages ALTER COLUMN message_id  TYPE TEXT;
ALTER TABLE email_messages ALTER COLUMN thread_id   TYPE TEXT;
```

`sender` and `recipient` stay `varchar(255)` (RFC 5321 caps both at 254 bytes).

`TEXT` and `varchar` share storage in PostgreSQL; no rewrite of existing rows. Indexes on `message_id` (if any) are recreated automatically by `ALTER COLUMN TYPE`.

### 5.2 New table `email_sync_errors`

```sql
CREATE TABLE email_sync_errors (
    id                   UUID PRIMARY KEY,
    mailbox_id           UUID NOT NULL REFERENCES mailboxes(id) ON DELETE CASCADE,
    sync_history_id      UUID REFERENCES sync_history(id) ON DELETE SET NULL,
    provider_message_id  TEXT,                              -- nullable: not all errors carry a message id
    subject              TEXT,                              -- truncated for storage / display
    sender               VARCHAR(255),
    error_type           VARCHAR(50)  NOT NULL,             -- see classifier below
    error_message        TEXT         NOT NULL,
    stack_trace          TEXT,                              -- populated when error_type='unexpected'
    raw_payload          JSONB,                             -- headers + classification result; NOT full body
    severity             VARCHAR(20)  NOT NULL DEFAULT 'medium',  -- low | medium | high
    status               VARCHAR(20)  NOT NULL DEFAULT 'pending', -- pending | retried | resolved | ignored | auto_recovered
    resolution           VARCHAR(50),                       -- user_ignored | user_retried_success | auto_recovered | admin_resolved
    retry_count          INTEGER      NOT NULL DEFAULT 0,
    last_retry_at        TIMESTAMPTZ,
    resolved_at          TIMESTAMPTZ,
    resolved_by_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_email_sync_errors_mailbox_status ON email_sync_errors(mailbox_id, status);
CREATE INDEX ix_email_sync_errors_type_created   ON email_sync_errors(error_type, created_at);
CREATE INDEX ix_email_sync_errors_created_at     ON email_sync_errors(created_at);
```

`raw_payload` carries provider-side headers and the partial classification result, not the full email body, to keep row size bounded and avoid duplicating large content already stored in `email_messages` when persistence partly succeeded.

## 6. Backend changes

### 6.1 New module `services/sync_error_classifier.py`

Pure function with no DB dependency, easy to unit-test:

```python
def classify_exception(exc: Exception) -> tuple[str, str]:
    """Return (error_type, severity)."""
    if isinstance(exc, sa_exc.DataError) and "value too long" in str(exc):
        return "schema_too_long", "medium"
    if isinstance(exc, UnicodeError):
        return "encoding_error", "medium"
    if isinstance(exc, sa_exc.IntegrityError):
        return "db_constraint", "medium"
    if isinstance(exc, ExtractionError):           # raised by services/ai_extraction
        return "extraction_failed", "low"
    return "unexpected", "high"
```

Severity is derived deterministically from `error_type`. `unexpected` is always `high` so it surfaces in admin filters.

### 6.2 New module `services/sync_error_recorder.py`

Single entry point:

```python
def record_sync_error(
    db: Session,
    mailbox: Mailbox,
    sync_history: SyncHistory | None,
    raw_email: dict,
    exc: Exception,
    error_type: str,
    severity: str,
) -> EmailSyncError
```

Responsibilities:
- Build the `EmailSyncError` row (truncated `subject`, redacted `raw_payload`).
- Persist in a fresh transaction (after the caller's `db.rollback()`).
- For `error_type='unexpected'`, additionally write a `severity='high'` row in `application_logs` so admins see it in the existing log viewer.
- Idempotent on `(mailbox_id, provider_message_id, error_type)` for the current `sync_history_id`: do not create duplicate rows if the same email fails twice in retry.

### 6.3 Resilient save loop

Edited inside the email sync sub-package (`backend/app/tasks/email_sync/`, exact module to be confirmed during implementation since the package was split in C1 Phase 8b). The wrapper logic from §4 sits at the innermost per-email boundary — currently inside `_sync_mailbox_async`'s batch loop.

Circuit breaker behaviour: after 5 consecutive `unexpected` errors, the loop sets the mailbox to `last_sync_status='failed'` with `last_sync_error_message='Circuit breaker tripped: too many unexpected errors'`, raises `SyncCircuitBreakerError`, and emits a `severity='high'` notification (see §6.6).

### 6.4 Truncate utility

New `backend/app/utils/string_truncate.py`:

```python
def truncate_to_bytes(value: str | None, max_bytes: int = 4096, marker: str = "[truncated]") -> str | None:
    """Cap byte length, append marker only when truncation occurred. Multi-byte safe."""
```

Applied in the email→DB mapper to `subject` and `sender_name` before the `INSERT`. `message_id` and `thread_id` are not truncated (they are provider IDs; if a provider returns oversized IDs that's a system-level failure we want to see, not silently mask).

### 6.5 Auto-recovery

Inside `process_single_email` *after* the email is successfully persisted to `email_messages`:

```python
db.execute(
    update(EmailSyncError)
    .where(
        EmailSyncError.mailbox_id == mailbox.id,
        EmailSyncError.provider_message_id == email["message_id"],
        EmailSyncError.status == "pending",
    )
    .values(status="auto_recovered", resolution="auto_recovered", resolved_at=now())
)
```

So when the user re-syncs after a fix has shipped, prior pending errors silently clear themselves.

### 6.6 Notifications

Emitted at the end of a sync, by a new helper `services/sync_notification_service.py`. Two new `notification_type` values:

- `sync_circuit_breaker` — emitted whenever the circuit breaker tripped during the sync. Payload includes mailbox id and error count. Severity high.
- `sync_skipped_many` — emitted only when `>10` emails were skipped during the sync AND the circuit breaker did not trip. Severity medium.

Below-threshold syncs (1–10 skips) emit no notification — the badge on the mailbox card and the admin dashboard are the only signal.

Both notification types deep-link to `/mailboxes/{id}/sync-errors`.

### 6.7 Endpoints

User-scoped (auth required, ownership enforced via `mailbox.user_id == current_user.id`):

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/mailboxes/{mailbox_id}/sync-errors` | Paginated list, filters: `status`, `error_type` |
| POST | `/api/mailboxes/{mailbox_id}/sync-errors/retry` | Enqueues `retry_skipped_emails(mailbox_id)`; 202 Accepted with task id |
| POST | `/api/sync-errors/{error_id}/ignore` | Mark `status=ignored, resolution=user_ignored` |

Admin-scoped (`Depends(require_admin)`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/admin/sync-errors` | Cross-user list, filters: `error_type`, `severity`, `status`, `mailbox_id`, date range |
| GET | `/api/admin/sync-errors/{error_id}` | Full row including `raw_payload`, `stack_trace` |
| POST | `/api/admin/sync-errors/{error_id}/resolve` | Mark `status=resolved, resolution=admin_resolved` |

### 6.8 Celery task `retry_skipped_emails`

```python
@celery_app.task(bind=True, max_retries=3)
def retry_skipped_emails(self, mailbox_id: UUID, error_ids: list[UUID] | None = None) -> dict:
    """Re-fetch and re-process the given pending errors (or all pending for the mailbox).
    Returns {"retried": N, "succeeded": M, "still_failing": K}."""
```

Behaviour:
- Re-fetch each email by `provider_message_id` via the existing provider abstraction.
- Run `process_single_email` again.
- On success → row marked `status=retried, resolution=user_retried_success`.
- On failure → `retry_count++`, `last_retry_at=now()`, error fields refreshed, `status` stays `pending`.
- Per-email isolation identical to the main sync loop (one bad retry does not abort the others).
- Idempotent: retrying an already-retried row is a no-op if it succeeded.

### 6.9 Zombie state fix

Cross-cutting: every `sync_mailbox_emails` Celery task wraps its main body so that on any unhandled exception (including `SyncCircuitBreakerError`), the mailbox transitions to `last_sync_status='failed'` with a meaningful `last_sync_error_message`, before re-raising. Implemented either as a context manager `_sync_status_guard(mailbox_id)` or a Celery `on_failure` handler — implementation choice deferred to the plan.

## 7. Frontend changes

### 7.1 User-facing — mailbox view

- Card badge: `⚠ N emails skipped` shown when `count(email_sync_errors WHERE status='pending') > 0`. The count comes from a small `count` field added to the existing mailbox detail response, not a second round trip.
- New route `/mailboxes/:id/sync-errors`, opened from the badge or the link in a notification.
- Page contents:
  - Filter bar: `status` (default `pending`), `error_type`.
  - Table: Date, Sender, Subject (first 80 chars), Error type (badge with i18n tooltip), Status.
  - Per-row action: `Ignore` (confirm dialog).
  - Global actions: `Retry all pending` (triggers Celery task; shows progress via existing job-progress WebSocket pattern), `Ignore all pending` (operates on `status='pending'` only, never on already-resolved rows).
  - Pagination via React Query infinite or page-based (match existing convention in the codebase).

i18n: a mapping `error_type → human message` lives in `frontend/src/i18n/locales/{en,fr}/syncErrors.json`. Example entries:

- `schema_too_long` → "Email too large for the current storage format. The team has been notified; retry once a fix is deployed."
- `encoding_error` → "Email contains invalid character encoding. Retry rarely succeeds; you can safely ignore."
- `extraction_failed` → "Subscription extraction failed for this email. Usually safe to retry."
- `db_constraint` → "Database constraint violation. Retry once a fix is deployed."
- `unexpected` → "An unexpected error occurred. The team has been notified."

New hook `useSyncErrors(mailboxId, filters)` using React Query, with cache invalidation after retry / ignore mutations.

### 7.2 Admin-facing — new page

`frontend/src/pages/admin/AdminSyncErrorsPage.tsx`, registered in `AdminLayout.tsx`.

- Top counters: total pending across all mailboxes, circuit breaker trips in last 7 days, top 5 `error_type` values by count.
- Table columns: Mailbox (email + provider icon), Error type, Severity, Status, Created at, Retry count.
- Filters: mailbox (dropdown), error_type, severity, status, date range.
- Click row → side drawer:
  - Full `error_message`.
  - `stack_trace` in monospace, collapsible.
  - `raw_payload` JSONB rendered as a tree, collapsible.
  - Action: `Mark resolved`.

### 7.3 Notifications

Existing `notifications` table and `NotificationsBell` component handle the new types out of the box. The only frontend work is mapping the two new `notification_type` values to icons and deep-link routes.

## 8. Risks & open questions

- **`raw_payload` size.** A misclassification could cause `raw_payload` to balloon. Mitigation: the recorder caps `raw_payload` JSONB serialised size (e.g. 16 KB) and stores a marker on overflow.
- **Auto-recovery race.** If a sync re-encounters the same `provider_message_id` and fails differently, the auto-recovery clause does not apply (we only update on success). Acceptable.
- **Retry storms.** A user clicking `Retry all pending` repeatedly could re-enqueue the same task. Mitigation: lock per `mailbox_id` similar to existing sync lock — the design chooses to reuse the same lock so a retry cannot race with a regular sync.
- **`provider_message_id` changes.** If a provider rotates message ids (Gmail does not in practice), retry breaks for old rows. Acceptable: such rows can be ignored.
- **Notification fatigue for large initial sync.** First-ever syncs of dusty mailboxes may exceed the 10-skip threshold. Mitigation: the threshold is a constant in code — easy to tune after observation.

## 9. Implementation order (informational, finalised in plan)

1. Migration (schema fix + new table).
2. New model + recorder + classifier + truncate utility, with unit tests.
3. Wrap the per-email save with try/except + circuit breaker, plus zombie-state guard.
4. Auto-recovery clause.
5. Endpoints (user + admin) with chartests against existing email_sync chartests staying green.
6. Celery `retry_skipped_emails` task.
7. Notification triggers.
8. Frontend user mailbox page + i18n.
9. Frontend admin page.
10. Manual end-to-end smoke test on the currently-stuck mailbox `ae421425-e840-41cd-92b1-d2934fa2efac`.

Each step is a candidate commit; whether they map to one PR or several is a question for the implementation plan, not this design.

## 10. Verification

- New unit tests on `classify_exception`, `truncate_to_bytes`, `record_sync_error`.
- New chartest verifying that a poisoned email in the middle of a batch leaves the other emails persisted and produces exactly one `email_sync_errors` row.
- New chartest verifying that 5 consecutive `unexpected` errors trip the circuit breaker and mark the mailbox `failed`.
- Existing `TestSyncInnerPipelineDedup` (5 chartests, C1 Phase 1) must remain green: the resilience wrapper is additive and must not change behaviour for happy-path emails.
- Manual: trigger a sync on a Gmail mailbox seeded with one oversized-subject email; observe one `email_sync_errors` row, batch completion, mailbox status `success`.
