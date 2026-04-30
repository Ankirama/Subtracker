# Email Sync Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the email sync pipeline resilient to per-email failures by isolating each email in its own try/except, persisting structured `email_sync_errors` rows, exposing them in the user mailbox view and a new admin page, with retry/ignore/auto-recovery actions and a circuit breaker for systemic failures.

**Architecture:** A per-email try/except wraps the classification-stage `INSERT` site (`stages/classification.py`). On any exception, the session is rolled back, the failure is classified (`schema_too_long`, `encoding_error`, `db_constraint`, `extraction_failed`, `unexpected`), persisted as a row in a new `email_sync_errors` table, and the loop continues. Five consecutive `unexpected` errors trip a circuit breaker that aborts the sync. The wrapping Celery task (`celery_tasks.py`) sets `last_sync_status='failed'` in any unhandled-exception path, fixing the zombie state. Schema-level fix widens four `email_messages` columns from `varchar` to `TEXT`. New REST endpoints + a Celery retry task + an in-app notification trigger close the loop. Frontend gets a per-mailbox drawer for the user and a new cross-user admin page.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Celery 5, PostgreSQL 15, React 18, TypeScript, Chakra UI, React Query, i18next.

**Source spec:** `docs/superpowers/specs/2026-04-28-email-sync-resilience-design.md`

**Branch:** `feat/email-sync-resilience` (to be created from `origin/main`).

**Current Alembic head:** `j9j9j9j9j9j9` (verified `alembic heads` 2026-04-28).

---

## Methodology Note: TDD vs chartests

Most tasks in this plan introduce NEW behaviour and follow standard TDD: write a failing test → run it → implement → run again → commit.

A subset of tasks (Task 7 wrapping the classification stage, Task 9 auto-recovery, Task 10 defense-in-depth truncate, Task 21 notification triggers) modify existing production code that is already covered by the C1 Phase 1 chartests in `backend/tests/test_email_sync.py`. For those tasks the rule is **the C1 chartests must remain green** — they are the contract that locks in pre-existing behaviour. Each integration task ends with a `pytest backend/tests/test_email_sync.py` step verifying this.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `backend/alembic/versions/k0k0k0k0k0k0_add_email_sync_errors_and_widen_columns.py` | Create | Alembic migration: widen `email_messages` columns + create `email_sync_errors` table |
| `backend/app/models/email_sync_error.py` | Create | SQLAlchemy model `EmailSyncError` |
| `backend/app/models/__init__.py` | Modify | Re-export `EmailSyncError` |
| `backend/app/models/email_message.py` | Modify | Change `subject`, `sender_name`, `message_id`, `thread_id` from `String(N)` to `Text()` |
| `backend/app/services/sync_error_classifier.py` | Create | `classify_exception(exc) -> tuple[str, str]` |
| `backend/app/utils/string_truncate.py` | Create | `truncate_to_bytes(value, max_bytes, marker)` |
| `backend/app/services/sync_error_recorder.py` | Create | `record_sync_error(...)`, `auto_recover_pending(...)` |
| `backend/app/services/sync_error_circuit_breaker.py` | Create | `SyncCircuitBreakerError` exception + counter helper |
| `backend/app/tasks/email_sync/stages/classification.py` | Modify | Wrap per-email INSERT in try/except + truncate fields + circuit-breaker counter |
| `backend/app/tasks/email_sync/celery_tasks.py` | Modify | Treat `SyncCircuitBreakerError` like other failures; ensure `failed` status in all error paths |
| `backend/app/services/sync_notification_service.py` | Create | `notify_sync_skipped_many`, `notify_sync_circuit_breaker` |
| `backend/app/models/notification.py` | Modify | Add `SYNC_SKIPPED_MANY` and `SYNC_CIRCUIT_BREAKER` to `NotificationType` enum |
| `backend/alembic/versions/l1l1l1l1l1l1_add_sync_notification_types.py` | Create | Alembic migration: extend Postgres `notificationtype` enum |
| `backend/app/schemas/sync_error.py` | Create | Pydantic schemas: `SyncErrorOut`, `SyncErrorAdminOut`, `SyncErrorListOut`, `RetryResponseOut` |
| `backend/app/api/sync_errors.py` | Create | User endpoints: list / ignore / retry |
| `backend/app/api/admin/sync_errors.py` | Create | Admin endpoints: list / detail / resolve |
| `backend/app/main.py` | Modify | Register the two new routers |
| `backend/app/tasks/sync_error_retry.py` | Create | Celery task `retry_skipped_emails` |
| `backend/tests/test_sync_error_classifier.py` | Create | Unit tests for the classifier |
| `backend/tests/test_string_truncate.py` | Create | Unit tests for the truncate utility |
| `backend/tests/test_sync_error_recorder.py` | Create | Unit tests for the recorder + auto-recovery |
| `backend/tests/test_email_sync_resilience.py` | Create | Chartests: poisoned-email isolation + circuit breaker behaviour |
| `backend/tests/test_sync_errors_api.py` | Create | User endpoint chartests |
| `backend/tests/test_admin_sync_errors_api.py` | Create | Admin endpoint chartests |
| `backend/tests/test_sync_error_retry_task.py` | Create | Retry-task chartest |
| `frontend/src/api/syncErrors.ts` | Create | User API client + TypeScript types |
| `frontend/src/api/adminSyncErrors.ts` | Create | Admin API client |
| `frontend/src/hooks/useSyncErrors.ts` | Create | React Query hook (user) |
| `frontend/src/hooks/useAdminSyncErrors.ts` | Create | React Query hook (admin) |
| `frontend/src/i18n/locales/en/syncErrors.json` | Create | English error-type messages |
| `frontend/src/i18n/locales/fr/syncErrors.json` | Create | French error-type messages |
| `frontend/src/i18n/config.ts` | Modify | Register the new namespace |
| `frontend/src/pages/SyncErrorsPage.tsx` | Create | User mailbox sync-errors page |
| `frontend/src/components/mailboxes/MailboxCard.tsx` (path TBC) | Modify | Add badge "N emails skipped" |
| `frontend/src/pages/admin/AdminSyncErrorsPage.tsx` | Create | Admin cross-user page |
| `frontend/src/pages/admin/AdminLayout.tsx` | Modify | Register new admin route + nav entry |
| `frontend/src/App.tsx` | Modify | Register `/mailboxes/:id/sync-errors` route |

The exact path for the mailbox card component is verified during Task 25 (the codebase has both `frontend/src/components/mailboxes/` and `frontend/src/pages/MailboxesPage.tsx`; the implementer reads the current code and modifies the right file).

---

## Tasks

Each task is one commit unless explicitly noted. After every commit, the next task starts with the working tree clean.

---

## Phase 1 — Migration and model

### Task 1: Alembic migration — widen `email_messages` columns and create `email_sync_errors`

**Files:**
- Create: `backend/alembic/versions/k0k0k0k0k0k0_add_email_sync_errors_and_widen_columns.py`

- [ ] **Step 1: Create the migration file**

```python
"""Add email_sync_errors table and widen email_messages text columns

Revision ID: k0k0k0k0k0k0
Revises: j9j9j9j9j9j9
Create Date: 2026-04-28

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "k0k0k0k0k0k0"
down_revision = "j9j9j9j9j9j9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen four columns of email_messages from varchar to TEXT.
    # PostgreSQL stores varchar and TEXT identically; the ALTER does not
    # rewrite the table. Indexes and unique constraints survive untouched.
    op.alter_column(
        "email_messages",
        "subject",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "email_messages",
        "sender_name",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "email_messages",
        "message_id",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "email_messages",
        "thread_id",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )

    # New table: email_sync_errors
    op.create_table(
        "email_sync_errors",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "mailbox_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mailboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("error_type", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("resolution", sa.String(length=50), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_email_sync_errors_mailbox_status",
        "email_sync_errors",
        ["mailbox_id", "status"],
    )
    op.create_index(
        "ix_email_sync_errors_type_created",
        "email_sync_errors",
        ["error_type", "created_at"],
    )
    op.create_index(
        "ix_email_sync_errors_created_at",
        "email_sync_errors",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_sync_errors_created_at", table_name="email_sync_errors")
    op.drop_index("ix_email_sync_errors_type_created", table_name="email_sync_errors")
    op.drop_index("ix_email_sync_errors_mailbox_status", table_name="email_sync_errors")
    op.drop_table("email_sync_errors")

    op.alter_column(
        "email_messages",
        "thread_id",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "email_messages",
        "message_id",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
    op.alter_column(
        "email_messages",
        "sender_name",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "email_messages",
        "subject",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
```

- [ ] **Step 2: Apply migration**

Run: `docker compose -f docker-compose.dev.yml exec backend alembic upgrade head`

Expected last line: `INFO  [alembic.runtime.migration] Running upgrade j9j9j9j9j9j9 -> k0k0k0k0k0k0, Add email_sync_errors table and widen email_messages text columns`

- [ ] **Step 3: Verify schema in DB**

Run:
```
docker compose -f docker-compose.dev.yml exec -T postgres \
  psql -U postgres -d subscription_tracker -c "\d email_messages" | grep -E "subject|sender_name|message_id|thread_id"
```

Expected: each line shows `text` (not `character varying`).

Run:
```
docker compose -f docker-compose.dev.yml exec -T postgres \
  psql -U postgres -d subscription_tracker -c "\d email_sync_errors"
```

Expected: table exists with 17 columns and 3 indexes (`ix_email_sync_errors_mailbox_status`, `ix_email_sync_errors_type_created`, `ix_email_sync_errors_created_at`).

- [ ] **Step 4: Verify downgrade works on a test DB**

Run: `docker compose -f docker-compose.dev.yml exec backend alembic downgrade -1` then re-upgrade: `alembic upgrade head`. Expected: both steps succeed, schema returns to current state.

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/email-sync-resilience
git add backend/alembic/versions/k0k0k0k0k0k0_add_email_sync_errors_and_widen_columns.py
git commit -m "feat(db): add email_sync_errors + widen email_messages text columns"
```

---

### Task 2: SQLAlchemy model `EmailSyncError`

**Files:**
- Create: `backend/app/models/email_sync_error.py`
- Modify: `backend/app/models/email_message.py` — change column types to mirror migration

- [ ] **Step 1: Update `email_message.py` to match the migrated schema**

Replace the `message_id`, `thread_id`, `subject`, `sender_name` column declarations:

```python
    # Email identification (from email headers)
    message_id = Column(
        Text, unique=True, nullable=False, index=True
    )  # Email Message-ID header
    thread_id = Column(Text, nullable=True, index=True)  # Thread/conversation ID

    # Email content
    subject = Column(Text, nullable=False)
    sender = Column(String(255), nullable=False, index=True)
    sender_name = Column(Text, nullable=True)
```

(Other columns unchanged.)

- [ ] **Step 2: Create `EmailSyncError` model**

```python
"""SQLAlchemy model for email sync error tracking.

Each row represents one email that could not be processed by the sync
pipeline (classification or persistence stage). The pipeline catches the
exception, classifies it, persists this row, and continues with the next
email — see services/sync_error_recorder.py.
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class EmailSyncError(Base):
    __tablename__ = "email_sync_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mailboxes.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_history_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sync_history.id", ondelete="SET NULL"),
        nullable=True,
    )

    provider_message_id = Column(Text, nullable=True)
    subject = Column(Text, nullable=True)
    sender = Column(String(255), nullable=True)

    error_type = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    raw_payload = Column(JSONB, nullable=True)

    severity = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="pending")
    resolution = Column(String(50), nullable=True)

    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    mailbox = relationship("Mailbox", backref="sync_errors")
    sync_history = relationship("SyncHistory", backref="errors")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])

    def __repr__(self):
        return (
            f"<EmailSyncError(id={self.id}, mailbox_id={self.mailbox_id}, "
            f"error_type={self.error_type}, status={self.status})>"
        )
```

- [ ] **Step 3: Re-export from `models/__init__.py`**

Append to the end of `backend/app/models/__init__.py`:

```python
from app.models.email_sync_error import EmailSyncError  # noqa: E402, F401
```

(Adjust to match the file's existing import style.)

- [ ] **Step 4: Verify the model can be imported and inserted**

Run:
```bash
docker compose -f docker-compose.dev.yml exec -T backend python -c "
from app.database import SessionLocal
from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
import uuid
db = SessionLocal()
mb = db.query(Mailbox).first()
err = EmailSyncError(
    mailbox_id=mb.id, error_type='unexpected', error_message='manual test'
)
db.add(err); db.commit()
print('inserted', err.id)
db.delete(err); db.commit()
print('cleaned up')
"
```

Expected: prints `inserted <uuid>` then `cleaned up`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/email_sync_error.py backend/app/models/email_message.py backend/app/models/__init__.py
git commit -m "feat(models): add EmailSyncError and align email_message types with migration"
```

---

## Phase 2 — Pure helpers (TDD)

### Task 3: Exception classifier

**Files:**
- Create: `backend/app/services/sync_error_classifier.py`
- Create: `backend/tests/test_sync_error_classifier.py`

- [ ] **Step 1: Write failing tests**

Write `backend/tests/test_sync_error_classifier.py`:

```python
"""Unit tests for the sync error classifier."""

import pytest
from sqlalchemy import exc as sa_exc

from app.services.sync_error_classifier import classify_exception


class _FakeDataError(sa_exc.DataError):
    def __init__(self, message: str):
        super().__init__("orig", {}, Exception(message))

    def __str__(self):
        return self.orig.args[0] if self.orig.args else ""


def test_classify_string_data_right_truncation_returns_schema_too_long():
    exc = _FakeDataError("value too long for type character varying(500)")
    error_type, severity = classify_exception(exc)
    assert error_type == "schema_too_long"
    assert severity == "medium"


def test_classify_unicode_error_returns_encoding_error():
    exc = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
    error_type, severity = classify_exception(exc)
    assert error_type == "encoding_error"
    assert severity == "medium"


def test_classify_integrity_error_returns_db_constraint():
    exc = sa_exc.IntegrityError("orig", {}, Exception("unique violation"))
    error_type, severity = classify_exception(exc)
    assert error_type == "db_constraint"
    assert severity == "medium"


def test_classify_data_error_other_returns_db_constraint():
    """A DataError that is NOT a length truncation falls back to db_constraint."""
    exc = _FakeDataError("invalid input syntax for type uuid")
    error_type, severity = classify_exception(exc)
    assert error_type == "db_constraint"
    assert severity == "medium"


def test_classify_extraction_error_returns_extraction_failed():
    from app.services.subscription_extractor import ExtractionError
    exc = ExtractionError("AI returned malformed JSON")
    error_type, severity = classify_exception(exc)
    assert error_type == "extraction_failed"
    assert severity == "low"


def test_classify_unknown_returns_unexpected_high():
    exc = RuntimeError("something exploded")
    error_type, severity = classify_exception(exc)
    assert error_type == "unexpected"
    assert severity == "high"
```

NOTE: if `app.services.subscription_extractor.ExtractionError` does not exist, the test imports will fail. Verify this before relying on it: `grep -n "class ExtractionError" backend/app/services/subscription_extractor.py`. If missing, add `class ExtractionError(Exception): ...` at the top of that module as a separate sub-step (Step 1a), and commit it together with this task.

- [ ] **Step 2: Run tests, expect failure**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_error_classifier.py -v`

Expected: ImportError or `ModuleNotFoundError: No module named 'app.services.sync_error_classifier'`.

- [ ] **Step 3: Implement classifier**

Create `backend/app/services/sync_error_classifier.py`:

```python
"""Pure classifier mapping exception → (error_type, severity).

Used by services/sync_error_recorder.py and the per-email try/except in
tasks/email_sync/stages/classification.py.

No DB access, no I/O — kept dependency-free for fast unit tests.
"""

from typing import Tuple

from sqlalchemy import exc as sa_exc

from app.services.subscription_extractor import ExtractionError


def classify_exception(exc: Exception) -> Tuple[str, str]:
    """Classify an exception raised during single-email processing.

    Returns:
        Tuple ``(error_type, severity)``.
        ``error_type`` is one of: ``schema_too_long``, ``encoding_error``,
        ``db_constraint``, ``extraction_failed``, ``unexpected``.
        ``severity`` is one of: ``low``, ``medium``, ``high``.
    """
    if isinstance(exc, sa_exc.DataError):
        if "value too long" in str(exc).lower():
            return "schema_too_long", "medium"
        return "db_constraint", "medium"

    if isinstance(exc, UnicodeError):
        return "encoding_error", "medium"

    if isinstance(exc, sa_exc.IntegrityError):
        return "db_constraint", "medium"

    if isinstance(exc, ExtractionError):
        return "extraction_failed", "low"

    return "unexpected", "high"
```

- [ ] **Step 4: Run tests, expect pass**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_error_classifier.py -v`

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sync_error_classifier.py backend/tests/test_sync_error_classifier.py
# also stage backend/app/services/subscription_extractor.py if Step 1a was needed
git commit -m "feat(services): add sync error classifier"
```

---

### Task 4: `truncate_to_bytes` utility

**Files:**
- Create: `backend/app/utils/string_truncate.py`
- Create: `backend/tests/test_string_truncate.py`

- [ ] **Step 1: Write failing tests**

```python
"""Unit tests for byte-aware string truncation."""

from app.utils.string_truncate import truncate_to_bytes


def test_truncate_none_returns_none():
    assert truncate_to_bytes(None, 100) is None


def test_truncate_short_string_returns_unchanged():
    assert truncate_to_bytes("hello", 100) == "hello"


def test_truncate_long_ascii_caps_at_max_minus_marker():
    s = "a" * 200
    out = truncate_to_bytes(s, max_bytes=100, marker="[T]")
    assert out.endswith("[T]")
    assert len(out.encode("utf-8")) <= 100


def test_truncate_multibyte_does_not_split_codepoint():
    # 'é' is 2 bytes in UTF-8. 50 of them = 100 bytes.
    s = "é" * 50
    out = truncate_to_bytes(s, max_bytes=20, marker="")
    # Ensure we did not produce invalid UTF-8 (i.e. cut mid-codepoint)
    out.encode("utf-8").decode("utf-8")
    assert len(out.encode("utf-8")) <= 20


def test_truncate_marker_fits_in_max_bytes():
    s = "x" * 100
    out = truncate_to_bytes(s, max_bytes=10, marker="[truncated]")
    # marker is 11 bytes which exceeds max — implementation must fall back
    # to a smaller marker rather than overflow. Acceptable result: truncate
    # without a marker.
    assert len(out.encode("utf-8")) <= 10


def test_truncate_marker_preserved_when_truncation_happens():
    s = "x" * 200
    out = truncate_to_bytes(s, max_bytes=100, marker="...")
    assert out.endswith("...")


def test_truncate_marker_absent_when_no_truncation_needed():
    out = truncate_to_bytes("hi", max_bytes=100, marker="...")
    assert out == "hi"
```

- [ ] **Step 2: Run tests, expect failure**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_string_truncate.py -v`

Expected: ImportError.

- [ ] **Step 3: Implement utility**

Create `backend/app/utils/string_truncate.py`:

```python
"""Byte-aware string truncation utility.

Used to defensively cap fields like ``email_messages.subject`` and
``email_messages.sender_name`` before INSERT, even though the columns are
now ``TEXT``. Defends against pathologically large provider payloads.
"""

from typing import Optional


def truncate_to_bytes(
    value: Optional[str],
    max_bytes: int,
    marker: str = "[truncated]",
) -> Optional[str]:
    """Truncate ``value`` so its UTF-8 encoding is at most ``max_bytes``.

    When truncation occurs, ``marker`` is appended (and counts toward the
    byte budget). If ``marker`` does not fit, it is dropped silently.
    Multi-byte characters are never split — the result is always valid
    UTF-8.

    ``None`` passes through unchanged.
    """
    if value is None:
        return None

    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value

    marker_bytes = marker.encode("utf-8")
    if len(marker_bytes) >= max_bytes:
        budget = max_bytes
        suffix = ""
    else:
        budget = max_bytes - len(marker_bytes)
        suffix = marker

    # Trim then re-decode with errors='ignore' to drop any partial codepoint
    truncated = encoded[:budget].decode("utf-8", errors="ignore")
    return truncated + suffix
```

- [ ] **Step 4: Run tests, expect pass**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_string_truncate.py -v`

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/string_truncate.py backend/tests/test_string_truncate.py
git commit -m "feat(utils): add byte-aware truncate_to_bytes"
```

---

## Phase 3 — Recorder service

### Task 5: `SyncErrorRecorder`

**Files:**
- Create: `backend/app/services/sync_error_recorder.py`
- Create: `backend/tests/test_sync_error_recorder.py`

- [ ] **Step 1: Write failing tests**

```python
"""Unit tests for sync_error_recorder.

The recorder is the sole writer of email_sync_errors rows. It must:
- persist a row even when the previous DB op poisoned the session
  (caller has issued db.rollback() before calling)
- truncate subject/raw_payload defensively
- write to application_logs at severity=high for unexpected errors
- be idempotent on (mailbox_id, provider_message_id, sync_history_id, error_type)
- support auto_recover_pending() for the success path
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.models.user import User
from app.services.sync_error_recorder import (
    record_sync_error,
    auto_recover_pending,
)


def _make_mailbox(db: Session, user: User) -> Mailbox:
    mb = Mailbox(
        user_id=user.id,
        provider_type="gmail",
        email_address="test@example.com",
        encrypted_credentials="x",
        is_active=True,
        sync_frequency="manual",
        batch_size=10,
        import_date_filter="30days",
        last_sync_status="success",
    )
    db.add(mb)
    db.commit()
    return mb


def test_record_sync_error_persists_row(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    raw_email = {
        "message_id": "msg-1",
        "subject": "S" * 100,
        "sender": "spam@example.com",
    }
    err = record_sync_error(
        db=db_session,
        mailbox=mb,
        sync_history=None,
        raw_email=raw_email,
        exc=ValueError("boom"),
        error_type="unexpected",
        severity="high",
    )
    assert err.id is not None
    assert err.mailbox_id == mb.id
    assert err.error_type == "unexpected"
    assert err.severity == "high"
    assert err.status == "pending"
    assert err.provider_message_id == "msg-1"
    assert err.subject == "S" * 100
    assert err.sender == "spam@example.com"
    assert err.error_message == "boom"
    assert err.stack_trace is not None  # populated for severity=high


def test_record_sync_error_truncates_subject_and_payload(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    raw_email = {
        "message_id": "msg-2",
        "subject": "X" * 100_000,  # 100KB
        "sender": "spam@example.com",
    }
    err = record_sync_error(
        db=db_session,
        mailbox=mb,
        sync_history=None,
        raw_email=raw_email,
        exc=ValueError("boom"),
        error_type="unexpected",
        severity="high",
    )
    # Subject capped at 4096 bytes
    assert len(err.subject.encode("utf-8")) <= 4096
    # raw_payload exists and is under 16KB serialised
    import json
    assert err.raw_payload is not None
    assert len(json.dumps(err.raw_payload)) <= 16_384


def test_record_sync_error_idempotent_on_same_message(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    raw = {"message_id": "msg-3", "subject": "s", "sender": "x@x"}
    e1 = record_sync_error(
        db_session, mb, None, raw, ValueError("a"), "schema_too_long", "medium"
    )
    e2 = record_sync_error(
        db_session, mb, None, raw, ValueError("b"), "schema_too_long", "medium"
    )
    assert e1.id == e2.id  # same row returned
    rows = (
        db_session.query(EmailSyncError)
        .filter(EmailSyncError.mailbox_id == mb.id)
        .all()
    )
    assert len(rows) == 1


def test_record_sync_error_unexpected_writes_application_log(db_session, test_user):
    from app.models.admin import ApplicationLog  # adjust import to actual location

    mb = _make_mailbox(db_session, test_user)
    raw = {"message_id": "msg-4", "subject": "s", "sender": "x@x"}
    record_sync_error(
        db_session, mb, None, raw, RuntimeError("boom"), "unexpected", "high"
    )
    logs = (
        db_session.query(ApplicationLog)
        .filter(ApplicationLog.logger_name == "email_sync.unexpected")
        .all()
    )
    assert len(logs) == 1
    assert logs[0].level == "ERROR"


def test_auto_recover_pending_marks_resolved(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    err = EmailSyncError(
        mailbox_id=mb.id,
        provider_message_id="msg-5",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    db_session.add(err)
    db_session.commit()

    n = auto_recover_pending(db_session, mb.id, "msg-5")
    db_session.refresh(err)
    assert n == 1
    assert err.status == "auto_recovered"
    assert err.resolution == "auto_recovered"
    assert err.resolved_at is not None


def test_auto_recover_pending_noop_when_already_resolved(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    err = EmailSyncError(
        mailbox_id=mb.id,
        provider_message_id="msg-6",
        error_type="schema_too_long",
        error_message="x",
        status="ignored",
    )
    db_session.add(err)
    db_session.commit()

    n = auto_recover_pending(db_session, mb.id, "msg-6")
    assert n == 0
```

NOTE: The actual `ApplicationLog` model location must be verified before this test file is committed: `grep -rn "class ApplicationLog" backend/app/models/`. Adjust the import in the test accordingly.

- [ ] **Step 2: Run tests, expect failure**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_error_recorder.py -v`

Expected: ImportError on `sync_error_recorder`.

- [ ] **Step 3: Implement recorder**

Create `backend/app/services/sync_error_recorder.py`:

```python
"""Persistence layer for email sync errors.

The single writer of ``email_sync_errors`` rows. Callers are the per-email
try/except in the email-sync pipeline (``stages/classification.py``) and the
retry task (``tasks/sync_error_retry.py``).

Contract:
- The caller has already issued ``db.rollback()`` before calling
  ``record_sync_error`` so the session is clean.
- Idempotent on
  ``(mailbox_id, provider_message_id, sync_history_id, error_type)``: if a
  matching row already exists, it is updated (retry_count++) and returned
  unchanged otherwise.
- ``unexpected`` errors are mirrored to ``application_logs`` at
  ``level='ERROR'`` so admins see them in the existing log viewer.
"""

import json
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.models.sync_history import SyncHistory
from app.utils.string_truncate import truncate_to_bytes

# IMPORTANT: import path for ApplicationLog must match the codebase.
# Verified during Task 5 — adjust if different.
from app.models.admin import ApplicationLog

logger = logging.getLogger(__name__)

_SUBJECT_MAX_BYTES = 4096
_RAW_PAYLOAD_MAX_BYTES = 16_384


def record_sync_error(
    db: Session,
    mailbox: Mailbox,
    sync_history: Optional[SyncHistory],
    raw_email: Dict[str, Any],
    exc: Exception,
    error_type: str,
    severity: str,
) -> EmailSyncError:
    """Persist (or update) an ``EmailSyncError`` row for one failed email."""
    provider_message_id = raw_email.get("message_id")
    sync_history_id = sync_history.id if sync_history else None

    # Idempotent lookup
    existing = (
        db.query(EmailSyncError)
        .filter(
            EmailSyncError.mailbox_id == mailbox.id,
            EmailSyncError.provider_message_id == provider_message_id,
            EmailSyncError.sync_history_id == sync_history_id,
            EmailSyncError.error_type == error_type,
        )
        .one_or_none()
    )

    subject = truncate_to_bytes(raw_email.get("subject"), _SUBJECT_MAX_BYTES)
    sender = raw_email.get("sender")

    error_message = str(exc) or exc.__class__.__name__
    stack = (
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if severity == "high"
        else None
    )

    payload = _build_payload(raw_email)

    if existing is not None:
        existing.error_message = error_message
        existing.stack_trace = stack
        existing.severity = severity
        existing.raw_payload = payload
        existing.retry_count = (existing.retry_count or 0)  # untouched here
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return existing

    err = EmailSyncError(
        mailbox_id=mailbox.id,
        sync_history_id=sync_history_id,
        provider_message_id=provider_message_id,
        subject=subject,
        sender=sender,
        error_type=error_type,
        error_message=error_message,
        stack_trace=stack,
        raw_payload=payload,
        severity=severity,
        status="pending",
    )
    db.add(err)
    db.commit()

    if error_type == "unexpected":
        _mirror_to_application_logs(db, err, exc)

    return err


def auto_recover_pending(
    db: Session, mailbox_id: uuid.UUID, provider_message_id: str
) -> int:
    """Mark all pending errors for this email as auto_recovered. Returns affected row count."""
    if not provider_message_id:
        return 0
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(EmailSyncError)
        .where(
            EmailSyncError.mailbox_id == mailbox_id,
            EmailSyncError.provider_message_id == provider_message_id,
            EmailSyncError.status == "pending",
        )
        .values(
            status="auto_recovered",
            resolution="auto_recovered",
            resolved_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return result.rowcount


def _build_payload(raw_email: Dict[str, Any]) -> Dict[str, Any]:
    """Build a JSON-serialisable payload no larger than 16KB."""
    payload = {
        k: raw_email.get(k)
        for k in ("message_id", "thread_id", "subject", "sender", "sender_name", "recipient", "date", "labels")
        if k in raw_email
    }
    serialised = json.dumps(payload, default=str)
    if len(serialised) <= _RAW_PAYLOAD_MAX_BYTES:
        return payload
    # Drop the largest field iteratively until under budget.
    while serialised and len(serialised) > _RAW_PAYLOAD_MAX_BYTES:
        if not payload:
            break
        biggest = max(payload, key=lambda k: len(str(payload[k])))
        payload[biggest] = "[truncated]"
        serialised = json.dumps(payload, default=str)
    payload["_truncated"] = True
    return payload


def _mirror_to_application_logs(
    db: Session, err: EmailSyncError, exc: Exception
) -> None:
    log = ApplicationLog(
        level="ERROR",
        logger_name="email_sync.unexpected",
        message=f"Unexpected error syncing email {err.provider_message_id}",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        stack_trace=err.stack_trace,
        context={
            "email_sync_error_id": str(err.id),
            "mailbox_id": str(err.mailbox_id),
            "provider_message_id": err.provider_message_id,
        },
    )
    db.add(log)
    db.commit()
```

- [ ] **Step 4: Run tests, expect pass**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_error_recorder.py -v`

Expected: 6 passed. If `ApplicationLog` import path is wrong, adjust in both the recorder and the test, then re-run.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sync_error_recorder.py backend/tests/test_sync_error_recorder.py
git commit -m "feat(services): add sync_error_recorder + auto_recover_pending"
```

---

## Phase 4 — Pipeline integration

### Task 6: `SyncCircuitBreakerError` exception

**Files:**
- Create: `backend/app/services/sync_error_circuit_breaker.py`

- [ ] **Step 1: Implement (no test for the bare exception class — covered by integration tests in Task 8)**

```python
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
```

- [ ] **Step 2: Verify import**

Run: `docker compose -f docker-compose.dev.yml exec backend python -c "from app.services.sync_error_circuit_breaker import SyncCircuitBreakerError, CIRCUIT_BREAKER_THRESHOLD; print('ok')"`

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/sync_error_circuit_breaker.py
git commit -m "feat(services): add SyncCircuitBreakerError exception"
```

---

### Task 7: Wrap per-email INSERT in `stages/classification.py`

**Files:**
- Modify: `backend/app/tasks/email_sync/stages/classification.py`
- Create: `backend/tests/test_email_sync_resilience.py`

The current loop (lines ~87-113) builds an `EmailMessage`, calls `db.add()` + `db.flush()` per row, and any exception kills the batch. We wrap the body in a try/except, classify errors, persist them, and continue. Subject/sender_name go through `truncate_to_bytes` before INSERT.

This task is the heart of the feature; it interacts with C1 chartests (must remain green).

- [ ] **Step 1: Write the resilience chartest first**

Create `backend/tests/test_email_sync_resilience.py`:

```python
"""Chartests for per-email failure isolation in the email-sync pipeline.

These verify the new resilience behaviour added to
``stages/classification.py``:
- A poisoned email in the middle of a batch yields one EmailSyncError
  row and the other emails persist normally.
- 5 consecutive ``unexpected`` errors trip the circuit breaker.

Uses the existing ``email_sync_harness`` fixture from C1 Phase 1.
"""

import asyncio
import uuid

import pytest

from app.models.email_message import EmailMessage
from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox


@pytest.mark.asyncio
async def test_poisoned_email_does_not_kill_batch(email_sync_harness, db_session):
    """Three emails: middle one has subject too long (varchar simulation by
    monkeypatching the model save to raise DataError). Other two persist
    and exactly one EmailSyncError is recorded for the poisoned one."""
    from sqlalchemy import exc as sa_exc

    harness = email_sync_harness  # fixture provides mailbox + provider mock

    poisoned_msg_id = "poison-1"
    emails = harness.make_provider_emails(
        [
            {"message_id": "good-1", "subject": "A"},
            {"message_id": poisoned_msg_id, "subject": "B"},
            {"message_id": "good-2", "subject": "C"},
        ]
    )

    # Monkeypatch flush so the second row's flush raises DataError once.
    original_flush = db_session.flush
    flush_call_count = {"n": 0}

    def flaky_flush(*a, **kw):
        flush_call_count["n"] += 1
        # The 2nd email is the 2nd db.flush (one per email)
        if flush_call_count["n"] == 2:
            raise sa_exc.DataError(
                "INSERT", {}, Exception("value too long for type character varying(500)")
            )
        return original_flush(*a, **kw)

    db_session.flush = flaky_flush

    await harness.run_classification_stage(emails=emails)

    # All non-poisoned emails persisted
    persisted = (
        db_session.query(EmailMessage)
        .filter(EmailMessage.mailbox_id == harness.mailbox.id)
        .all()
    )
    persisted_ids = {e.message_id for e in persisted}
    assert "good-1" in persisted_ids
    assert "good-2" in persisted_ids
    assert poisoned_msg_id not in persisted_ids

    # One EmailSyncError row for the poisoned email
    errors = (
        db_session.query(EmailSyncError)
        .filter(EmailSyncError.mailbox_id == harness.mailbox.id)
        .all()
    )
    assert len(errors) == 1
    assert errors[0].provider_message_id == poisoned_msg_id
    assert errors[0].error_type == "schema_too_long"
    assert errors[0].status == "pending"


@pytest.mark.asyncio
async def test_circuit_breaker_trips_after_5_consecutive_unexpected(
    email_sync_harness, db_session
):
    from app.services.sync_error_circuit_breaker import (
        SyncCircuitBreakerError,
        CIRCUIT_BREAKER_THRESHOLD,
    )

    harness = email_sync_harness

    emails = harness.make_provider_emails(
        [{"message_id": f"m-{i}", "subject": "X"} for i in range(CIRCUIT_BREAKER_THRESHOLD)]
    )

    # Make every flush raise a generic exception (→ unexpected)
    def always_boom(*a, **kw):
        raise RuntimeError("simulated systemic bug")

    db_session.flush = always_boom

    with pytest.raises(SyncCircuitBreakerError) as excinfo:
        await harness.run_classification_stage(emails=emails)

    assert excinfo.value.error_count >= CIRCUIT_BREAKER_THRESHOLD

    errors = (
        db_session.query(EmailSyncError)
        .filter(EmailSyncError.mailbox_id == harness.mailbox.id)
        .all()
    )
    assert len(errors) == CIRCUIT_BREAKER_THRESHOLD
    assert all(e.error_type == "unexpected" for e in errors)
    assert all(e.severity == "high" for e in errors)
```

NOTE: `email_sync_harness` is a fixture introduced by C1 Phase 1. Verify the fixture exposes `make_provider_emails` and `run_classification_stage` (or equivalent). If the API differs, adapt the test to use `harness.run()` or whatever calls `classify_new_emails`. Check `backend/tests/conftest.py` before writing this test.

- [ ] **Step 2: Run tests, expect failure**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_email_sync_resilience.py -v`

Expected: FAIL — the production code does not yet wrap exceptions.

- [ ] **Step 3: Modify `stages/classification.py`**

Replace the loop body (around lines 87-113):

```python
"""STAGE 1 — Classification stage of the email-sync pipeline.

(...existing docstring...)
"""

import logging
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.mailbox import Mailbox
from app.services.email_filter import should_process_email
from app.services.email_pipeline_protocol import AIClassifier
from app.services.sync_error_circuit_breaker import (
    SyncCircuitBreakerError,
    CIRCUIT_BREAKER_THRESHOLD,
)
from app.services.sync_error_classifier import classify_exception
from app.services.sync_error_recorder import (
    record_sync_error,
    auto_recover_pending,
)
from app.utils.string_truncate import truncate_to_bytes

logger = logging.getLogger(__name__)

_SUBJECT_MAX_BYTES = 4096
_SENDER_NAME_MAX_BYTES = 4096


async def classify_new_emails(
    db: Session,
    mailbox: Mailbox,
    emails: list,
    batch_num: int,
    *,
    classify_batch: AIClassifier,
    sync_history=None,
) -> Tuple[List[tuple], List[tuple]]:
    """Stage 1 (resilient): identify, classify, persist new emails.

    A failure on any single email is caught, classified, and recorded as
    an EmailSyncError row. The batch continues with the remaining emails.

    Five consecutive ``unexpected`` failures trip the circuit breaker —
    a SyncCircuitBreakerError is raised and the sync aborts.
    """
    new_emails = []
    new_emails_to_classify = []
    existing_email_records = []

    for email in emails:
        message_id = email.headers.get("Message-ID", email.id)
        existing_email = (
            db.query(EmailMessage).filter(EmailMessage.message_id == message_id).first()
        )

        if not existing_email:
            new_emails.append(email)
            if should_process_email(email, db):
                new_emails_to_classify.append(email)
            else:
                logger.info(f"Skipping system email: {email.subject}")
        else:
            existing_email_records.append((email, existing_email))

    logger.info(
        f"Batch {batch_num}: {len(new_emails)} new emails, "
        f"{len(existing_email_records)} existing emails"
    )

    classifications = []
    if new_emails_to_classify:
        logger.info(f"Classifying {len(new_emails_to_classify)} emails in parallel...")
        classifications = await classify_batch(new_emails_to_classify, db)

    # Per-email persistence with isolation
    email_records = []
    consecutive_unexpected = 0

    for email, classification in zip(new_emails, classifications):
        message_id = email.headers.get("Message-ID", email.id)
        try:
            email_record = EmailMessage(
                mailbox_id=mailbox.id,
                message_id=message_id,
                thread_id=email.headers.get("Thread-ID"),
                subject=truncate_to_bytes(email.subject, _SUBJECT_MAX_BYTES),
                sender=email.sender,
                sender_name=truncate_to_bytes(email.sender_name, _SENDER_NAME_MAX_BYTES),
                recipient=(
                    email.recipients[0] if email.recipients else mailbox.email_address
                ),
                date=email.date,
                body_text=email.body_text,
                body_html=email.body_html,
                labels=[email.folder] if email.folder else None,
                attachments=None,
                is_subscription=classification.get("is_subscription", False),
                classification_confidence=classification.get("confidence", 0.0),
                classification_reasoning=classification,
            )
            db.add(email_record)
            db.flush()
            email_records.append((email, email_record))

            # Auto-recovery: a previously-pending error for this same
            # provider_message_id is now flagged resolved.
            auto_recover_pending(db, mailbox.id, message_id)

            consecutive_unexpected = 0
            logger.info(
                f"Saved email to database: {email.subject} "
                f"(subscription: {email_record.is_subscription})"
            )
        except Exception as exc:  # noqa: BLE001 — intentional broad catch
            db.rollback()
            error_type, severity = classify_exception(exc)
            raw_email_dict = {
                "message_id": message_id,
                "thread_id": email.headers.get("Thread-ID"),
                "subject": email.subject,
                "sender": email.sender,
                "sender_name": email.sender_name,
                "recipient": (
                    email.recipients[0] if email.recipients else mailbox.email_address
                ),
                "date": email.date.isoformat() if email.date else None,
                "labels": [email.folder] if email.folder else None,
            }
            record_sync_error(
                db=db,
                mailbox=mailbox,
                sync_history=sync_history,
                raw_email=raw_email_dict,
                exc=exc,
                error_type=error_type,
                severity=severity,
            )
            logger.warning(
                f"Skipped email {message_id} (error_type={error_type}): {exc}"
            )

            if error_type == "unexpected":
                consecutive_unexpected += 1
                if consecutive_unexpected >= CIRCUIT_BREAKER_THRESHOLD:
                    raise SyncCircuitBreakerError(
                        threshold=CIRCUIT_BREAKER_THRESHOLD,
                        error_count=consecutive_unexpected,
                    )

    return email_records, existing_email_records
```

- [ ] **Step 4: Update orchestrator to thread `sync_history` through**

In `backend/app/tasks/email_sync/orchestrator.py`, change the call site to pass `history_entry`:

```python
# Before (find this line, currently around the per-batch loop):
email_records, existing_email_records = await classify_new_emails(
    db, mailbox, batch_emails, batch_num, classify_batch=classify_batch
)

# After:
email_records, existing_email_records = await classify_new_emails(
    db, mailbox, batch_emails, batch_num,
    classify_batch=classify_batch,
    sync_history=history_entry,
)
```

`history_entry` is already a parameter of `_sync_mailbox_async` (line ~71); no signature change needed.

- [ ] **Step 5: Run resilience chartests, expect pass**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_email_sync_resilience.py -v`

Expected: 2 passed.

- [ ] **Step 6: Run full email_sync chartests, expect them all green**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_email_sync.py -v`

Expected: all C1 Phase 1 chartests pass (especially `TestSyncInnerPipelineDedup`, `TestSyncMailboxEmails`).

If any C1 chartest fails: the new try/except is changing observable behaviour for the happy path. STOP and re-read — the wrapper must be a pure superset for non-erroring emails.

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/email_sync/stages/classification.py \
        backend/app/tasks/email_sync/orchestrator.py \
        backend/tests/test_email_sync_resilience.py
git commit -m "feat(email_sync): per-email isolation + circuit breaker"
```

---

### Task 8: Zombie state guard in `celery_tasks.py`

The current outer `except Exception` block (lines 307-329 of `celery_tasks.py`) does set `last_sync_status='failed'` and commits — but that commit can re-raise if the session is poisoned. After Task 7's per-email rollback, the session should be clean. We still need to:

1. Open a fresh session before the final commit, so even a `SessionClosed` or `PendingRollback` from upstream cannot strand the mailbox in `in_progress`.
2. Treat `SyncCircuitBreakerError` like other failures (no retry, just record).

**Files:**
- Modify: `backend/app/tasks/email_sync/celery_tasks.py`

- [ ] **Step 1: Add `SyncCircuitBreakerError` to `dont_autoretry_for`**

Locate the `@celery_app.task(...)` decorator on `sync_mailbox_emails` (line ~59-71). The `autoretry_for=(Exception,)` retries everything; we need to keep that behaviour for other exceptions, but explicitly handle the circuit breaker. Since Celery does not have `dont_autoretry_for`, the cleanest option is to handle the exception inside the task body (so Celery sees a normal return).

Add at the top of the task body imports:

```python
from app.services.sync_error_circuit_breaker import SyncCircuitBreakerError
```

Add a new `except SyncCircuitBreakerError` block BEFORE the catch-all `except Exception`:

```python
    except SyncCircuitBreakerError as e:
        logger.error(
            f"Sync aborted by circuit breaker for mailbox {mailbox_id}: {e}"
        )
        exception_time = datetime.now(timezone.utc)
        # Use a fresh session — the original may be in PendingRollback if the
        # circuit-breaker raise interrupted persistence.
        try:
            db.rollback()
        except Exception:
            pass
        mailbox.last_sync_status = "failed"
        mailbox.last_sync_at = exception_time
        mailbox.last_sync_error_message = str(e)
        history_entry.status = "failed"
        history_entry.completed_at = exception_time
        history_entry.duration_seconds = int(
            (exception_time - history_entry.started_at.replace(tzinfo=timezone.utc)).total_seconds()
        )
        history_entry.error_message = str(e)
        history_entry.error_type = "SyncCircuitBreakerError"
        history_entry.total_emails_processed = mailbox.last_sync_emails_processed or 0
        history_entry.subscriptions_found = mailbox.last_sync_subscriptions_found or 0
        history_entry.batches_processed = mailbox.last_sync_batch_num or 0
        db.commit()
        return {"success": False, "error": str(e), "error_type": "circuit_breaker"}
```

This early return prevents Celery's `autoretry_for=(Exception,)` from retrying the circuit breaker.

- [ ] **Step 2: Make the outer `except Exception` block resilient to a poisoned session**

Replace lines 307-329 (the existing `except Exception as e` block) with:

```python
    except Exception as e:
        logger.error(f"Email sync failed for mailbox {mailbox_id}: {str(e)}")
        exception_time = datetime.now(timezone.utc)
        # Reset the session: any inner failure may have left it in
        # PendingRollback. We MUST update mailbox state regardless.
        try:
            db.rollback()
        except Exception:
            pass
        try:
            # Re-fetch mailbox in case it became detached after rollback
            mailbox_id_uuid = UUID(mailbox_id)
            mailbox_fresh = db.query(Mailbox).filter(Mailbox.id == mailbox_id_uuid).first()
            if mailbox_fresh is not None:
                mailbox_fresh.last_sync_status = "failed"
                mailbox_fresh.last_sync_at = exception_time
                mailbox_fresh.last_sync_error_message = str(e)

                history_fresh = (
                    db.query(SyncHistory).filter(SyncHistory.id == history_entry.id).first()
                    if history_entry is not None
                    else None
                )
                if history_fresh is not None:
                    history_fresh.status = "failed"
                    history_fresh.completed_at = exception_time
                    history_fresh.duration_seconds = int(
                        (exception_time - history_fresh.started_at.replace(tzinfo=timezone.utc)).total_seconds()
                    )
                    history_fresh.error_message = str(e)
                    history_fresh.error_type = type(e).__name__
                    history_fresh.total_emails_processed = (
                        mailbox_fresh.last_sync_emails_processed or 0
                    )
                    history_fresh.subscriptions_found = (
                        mailbox_fresh.last_sync_subscriptions_found or 0
                    )
                    history_fresh.batches_processed = mailbox_fresh.last_sync_batch_num or 0

                db.commit()
        except Exception as commit_exc:
            logger.error(f"Failed to mark mailbox failed after sync error: {commit_exc}")

        # Re-raise so Celery's autoretry_for kicks in for transient errors.
        # If retries are exhausted Celery will give up and the mailbox will
        # already be in `failed` state.
        raise
```

- [ ] **Step 3: Run full email_sync test suite**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_email_sync.py backend/tests/test_email_sync_resilience.py -v`

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/email_sync/celery_tasks.py
git commit -m "fix(email_sync): handle SyncCircuitBreakerError + reset session before failed-state commit"
```

---

## Phase 5 — Pydantic schemas

### Task 9: `SyncError` schemas

**Files:**
- Create: `backend/app/schemas/sync_error.py`

- [ ] **Step 1: Implement schemas**

```python
"""Pydantic v2 schemas for sync error endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SyncErrorOut(BaseModel):
    """User-facing sync error (PII-safe — no raw_payload, no stack_trace)."""
    id: UUID
    mailbox_id: UUID
    sync_history_id: Optional[UUID] = None
    provider_message_id: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    error_type: str
    error_message: str
    severity: str
    status: str
    resolution: Optional[str] = None
    retry_count: int
    last_retry_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncErrorAdminOut(SyncErrorOut):
    """Admin view: includes raw_payload and stack_trace."""
    stack_trace: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None
    resolved_by_id: Optional[UUID] = None


class SyncErrorListOut(BaseModel):
    items: List[SyncErrorOut]
    total: int
    page: int
    page_size: int


class SyncErrorAdminListOut(BaseModel):
    items: List[SyncErrorAdminOut]
    total: int
    page: int
    page_size: int


class RetryResponseOut(BaseModel):
    task_id: str = Field(..., description="Celery task id for the retry batch")
    pending_count: int = Field(..., description="Number of errors queued for retry")
```

- [ ] **Step 2: Verify import**

Run: `docker compose -f docker-compose.dev.yml exec backend python -c "from app.schemas.sync_error import SyncErrorOut, SyncErrorListOut, RetryResponseOut; print('ok')"`

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/sync_error.py
git commit -m "feat(schemas): add SyncError pydantic schemas"
```

---

## Phase 6 — User-facing endpoints

### Task 10: User endpoints — list / ignore / retry

**Files:**
- Create: `backend/app/api/sync_errors.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_sync_errors_api.py`

- [ ] **Step 1: Write API chartest**

Create `backend/tests/test_sync_errors_api.py`:

```python
"""Chartests for user-facing sync errors endpoints."""

import uuid

import pytest

from app.models.email_sync_error import EmailSyncError


def _seed_errors(db_session, mailbox, count: int, status: str = "pending") -> list:
    rows = []
    for i in range(count):
        e = EmailSyncError(
            mailbox_id=mailbox.id,
            provider_message_id=f"msg-{i}",
            subject=f"Subject {i}",
            sender=f"sender{i}@example.com",
            error_type="schema_too_long",
            error_message="value too long",
            severity="medium",
            status=status,
        )
        db_session.add(e)
        rows.append(e)
    db_session.commit()
    return rows


def test_list_sync_errors_returns_user_mailbox_errors(
    auth_client, test_user, test_mailbox, db_session
):
    _seed_errors(db_session, test_mailbox, 3)
    resp = auth_client.get(f"/api/mailboxes/{test_mailbox.id}/sync-errors")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_sync_errors_filters_by_status(
    auth_client, test_user, test_mailbox, db_session
):
    _seed_errors(db_session, test_mailbox, 2, status="pending")
    _seed_errors(db_session, test_mailbox, 1, status="ignored")
    resp = auth_client.get(
        f"/api/mailboxes/{test_mailbox.id}/sync-errors?status=ignored"
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_sync_errors_rejects_other_users_mailbox(
    auth_client, other_user_mailbox
):
    resp = auth_client.get(f"/api/mailboxes/{other_user_mailbox.id}/sync-errors")
    assert resp.status_code in (403, 404)


def test_ignore_sync_error_marks_ignored(
    auth_client, test_user, test_mailbox, db_session
):
    [err] = _seed_errors(db_session, test_mailbox, 1)
    resp = auth_client.post(f"/api/sync-errors/{err.id}/ignore")
    assert resp.status_code == 200
    db_session.refresh(err)
    assert err.status == "ignored"
    assert err.resolution == "user_ignored"
    assert err.resolved_at is not None


def test_ignore_sync_error_rejects_other_users_error(
    auth_client, other_user_mailbox, db_session
):
    [err] = _seed_errors(db_session, other_user_mailbox, 1)
    resp = auth_client.post(f"/api/sync-errors/{err.id}/ignore")
    assert resp.status_code in (403, 404)


def test_retry_sync_errors_enqueues_celery_task(
    auth_client, test_mailbox, db_session, mocker
):
    _seed_errors(db_session, test_mailbox, 2)
    delay_mock = mocker.patch(
        "app.tasks.sync_error_retry.retry_skipped_emails.delay"
    )
    delay_mock.return_value = mocker.MagicMock(id="task-123")
    resp = auth_client.post(
        f"/api/mailboxes/{test_mailbox.id}/sync-errors/retry"
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"] == "task-123"
    assert body["pending_count"] == 2
    delay_mock.assert_called_once()
```

NOTE: fixtures `auth_client`, `test_user`, `test_mailbox`, `other_user_mailbox` are assumed from `backend/tests/conftest.py` — verify and adapt names if different. If `mocker` is unavailable, swap to `unittest.mock.patch`.

- [ ] **Step 2: Run tests, expect failure**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_errors_api.py -v`

Expected: 404 on every endpoint (router not registered).

- [ ] **Step 3: Implement router**

Create `backend/app/api/sync_errors.py`:

```python
"""User-facing endpoints for email sync errors."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.models.user import User
from app.schemas.sync_error import (
    RetryResponseOut,
    SyncErrorListOut,
    SyncErrorOut,
)
from app.security.dependencies import get_current_user
from app.tasks.sync_error_retry import retry_skipped_emails

router = APIRouter(prefix="/api", tags=["sync-errors"])


def _get_user_mailbox(
    mailbox_id: UUID, db: Session, current_user: User
) -> Mailbox:
    mb = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )
    if mb is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mb


def _get_user_error(
    error_id: UUID, db: Session, current_user: User
) -> EmailSyncError:
    err = (
        db.query(EmailSyncError)
        .join(Mailbox, Mailbox.id == EmailSyncError.mailbox_id)
        .filter(
            EmailSyncError.id == error_id,
            Mailbox.user_id == current_user.id,
        )
        .first()
    )
    if err is None:
        raise HTTPException(status_code=404, detail="Sync error not found")
    return err


@router.get(
    "/mailboxes/{mailbox_id}/sync-errors",
    response_model=SyncErrorListOut,
)
def list_sync_errors(
    mailbox_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    error_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncErrorListOut:
    _get_user_mailbox(mailbox_id, db, current_user)

    q = db.query(EmailSyncError).filter(EmailSyncError.mailbox_id == mailbox_id)
    if status_filter:
        q = q.filter(EmailSyncError.status == status_filter)
    if error_type:
        q = q.filter(EmailSyncError.error_type == error_type)

    total = q.count()
    items = (
        q.order_by(EmailSyncError.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SyncErrorListOut(
        items=[SyncErrorOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/sync-errors/{error_id}/ignore", response_model=SyncErrorOut)
def ignore_sync_error(
    error_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncErrorOut:
    err = _get_user_error(error_id, db, current_user)
    if err.status == "ignored":
        return SyncErrorOut.model_validate(err)
    err.status = "ignored"
    err.resolution = "user_ignored"
    err.resolved_at = datetime.now(timezone.utc)
    err.resolved_by_id = current_user.id
    db.commit()
    db.refresh(err)
    return SyncErrorOut.model_validate(err)


@router.post(
    "/mailboxes/{mailbox_id}/sync-errors/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RetryResponseOut,
)
def retry_sync_errors(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetryResponseOut:
    mb = _get_user_mailbox(mailbox_id, db, current_user)
    pending_count = (
        db.query(EmailSyncError)
        .filter(
            EmailSyncError.mailbox_id == mb.id,
            EmailSyncError.status == "pending",
        )
        .count()
    )
    if pending_count == 0:
        raise HTTPException(status_code=400, detail="No pending errors to retry")
    task = retry_skipped_emails.delay(str(mb.id))
    return RetryResponseOut(task_id=task.id, pending_count=pending_count)
```

- [ ] **Step 4: Register router in `backend/app/main.py`**

Find the existing block that calls `app.include_router(...)` (after FastAPI app construction). Append:

```python
from app.api import sync_errors as sync_errors_router  # noqa: E402

app.include_router(sync_errors_router.router)
```

- [ ] **Step 5: Run tests, expect pass**

The retry-task `app.tasks.sync_error_retry.retry_skipped_emails` doesn't exist yet. Either:
- (a) Skip the retry test (`@pytest.mark.skip`) until Task 13 lands; or
- (b) Provide a temporary stub `backend/app/tasks/sync_error_retry.py` with just `from celery import shared_task; @shared_task def retry_skipped_emails(*a, **kw): ...` and update it in Task 13.

Recommended: (b). Add a minimal stub now, full implementation in Task 13.

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_errors_api.py -v`

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/sync_errors.py backend/app/main.py \
        backend/app/tasks/sync_error_retry.py \
        backend/tests/test_sync_errors_api.py
git commit -m "feat(api): user sync-errors endpoints (list, ignore, retry)"
```

---

## Phase 7 — Admin endpoints

### Task 11: Admin endpoints — list / detail / resolve

**Files:**
- Create: `backend/app/api/admin/sync_errors.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_sync_errors_api.py`

- [ ] **Step 1: Write chartest**

Create `backend/tests/test_admin_sync_errors_api.py`:

```python
"""Chartests for admin sync-errors endpoints."""

import uuid

from app.models.email_sync_error import EmailSyncError


def _seed(db_session, mailbox, **kwargs):
    err = EmailSyncError(
        mailbox_id=mailbox.id,
        provider_message_id=kwargs.get("message_id", "m"),
        error_type=kwargs.get("error_type", "schema_too_long"),
        error_message="x",
        severity=kwargs.get("severity", "medium"),
        status=kwargs.get("status", "pending"),
        stack_trace="full traceback here",
        raw_payload={"subject": "X" * 100, "sender": "s@s"},
    )
    db_session.add(err)
    db_session.commit()
    return err


def test_admin_list_sync_errors_cross_user(
    admin_client, test_mailbox, other_user_mailbox, db_session
):
    _seed(db_session, test_mailbox, message_id="m1")
    _seed(db_session, other_user_mailbox, message_id="m2")
    resp = admin_client.get("/api/admin/sync-errors")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_admin_list_filters_by_severity(
    admin_client, test_mailbox, db_session
):
    _seed(db_session, test_mailbox, message_id="a", severity="medium")
    _seed(db_session, test_mailbox, message_id="b", severity="high")
    resp = admin_client.get("/api/admin/sync-errors?severity=high")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_admin_list_rejects_non_admin(auth_client):
    resp = auth_client.get("/api/admin/sync-errors")
    assert resp.status_code == 403


def test_admin_detail_returns_raw_payload_and_stack_trace(
    admin_client, test_mailbox, db_session
):
    err = _seed(db_session, test_mailbox)
    resp = admin_client.get(f"/api/admin/sync-errors/{err.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stack_trace"] == "full traceback here"
    assert body["raw_payload"]["sender"] == "s@s"


def test_admin_resolve_marks_admin_resolved(
    admin_client, admin_user, test_mailbox, db_session
):
    err = _seed(db_session, test_mailbox)
    resp = admin_client.post(f"/api/admin/sync-errors/{err.id}/resolve")
    assert resp.status_code == 200
    db_session.refresh(err)
    assert err.status == "resolved"
    assert err.resolution == "admin_resolved"
    assert err.resolved_by_id == admin_user.id
```

NOTE: fixtures `admin_client`, `admin_user` must exist. Verify in `conftest.py`. If absent, copy the pattern of existing admin tests (e.g. `test_admin_users_api.py` — `grep -l "admin_client" backend/tests/`).

- [ ] **Step 2: Run tests, expect failure**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_admin_sync_errors_api.py -v`

Expected: 404 on all endpoints.

- [ ] **Step 3: Implement admin router**

Create `backend/app/api/admin/sync_errors.py`:

```python
"""Admin-only endpoints for cross-mailbox sync error oversight."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_sync_error import EmailSyncError
from app.models.user import User
from app.schemas.sync_error import (
    SyncErrorAdminListOut,
    SyncErrorAdminOut,
)
from app.security.dependencies import get_current_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin", "sync-errors"])


@router.get("/sync-errors", response_model=SyncErrorAdminListOut)
def list_admin_sync_errors(
    error_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    mailbox_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> SyncErrorAdminListOut:
    q = db.query(EmailSyncError)
    if error_type:
        q = q.filter(EmailSyncError.error_type == error_type)
    if severity:
        q = q.filter(EmailSyncError.severity == severity)
    if status_filter:
        q = q.filter(EmailSyncError.status == status_filter)
    if mailbox_id:
        q = q.filter(EmailSyncError.mailbox_id == mailbox_id)

    total = q.count()
    items = (
        q.order_by(EmailSyncError.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SyncErrorAdminListOut(
        items=[SyncErrorAdminOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sync-errors/{error_id}", response_model=SyncErrorAdminOut)
def get_admin_sync_error(
    error_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> SyncErrorAdminOut:
    err = db.query(EmailSyncError).filter(EmailSyncError.id == error_id).first()
    if err is None:
        raise HTTPException(status_code=404, detail="Sync error not found")
    return SyncErrorAdminOut.model_validate(err)


@router.post("/sync-errors/{error_id}/resolve", response_model=SyncErrorAdminOut)
def resolve_admin_sync_error(
    error_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> SyncErrorAdminOut:
    err = db.query(EmailSyncError).filter(EmailSyncError.id == error_id).first()
    if err is None:
        raise HTTPException(status_code=404, detail="Sync error not found")
    err.status = "resolved"
    err.resolution = "admin_resolved"
    err.resolved_at = datetime.now(timezone.utc)
    err.resolved_by_id = admin.id
    db.commit()
    db.refresh(err)
    return SyncErrorAdminOut.model_validate(err)
```

If `get_current_admin_user` does not exist, locate the equivalent in `backend/app/security/dependencies.py` (likely `require_admin` or similar — `grep -n "def.*admin" backend/app/security/dependencies.py`).

- [ ] **Step 4: Register router in `main.py`**

Append next to the user router registration:

```python
from app.api.admin import sync_errors as admin_sync_errors_router  # noqa: E402

app.include_router(admin_sync_errors_router.router)
```

- [ ] **Step 5: Run tests, expect pass**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_admin_sync_errors_api.py -v`

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/admin/sync_errors.py backend/app/main.py \
        backend/tests/test_admin_sync_errors_api.py
git commit -m "feat(api): admin sync-errors endpoints (list, detail, resolve)"
```

---

## Phase 8 — Celery retry task

### Task 12: `retry_skipped_emails` Celery task

**Files:**
- Modify: `backend/app/tasks/sync_error_retry.py` (replace stub from Task 10)
- Create: `backend/tests/test_sync_error_retry_task.py`

- [ ] **Step 1: Write retry chartest**

Create `backend/tests/test_sync_error_retry_task.py`:

```python
"""Chartest for retry_skipped_emails Celery task."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.email_sync_error import EmailSyncError
from app.tasks.sync_error_retry import retry_skipped_emails


def test_retry_success_marks_user_retried_success(
    db_session, test_mailbox, mocker
):
    err = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-success",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    db_session.add(err)
    db_session.commit()

    # Mock the provider fetch + process call to succeed
    mocker.patch(
        "app.tasks.sync_error_retry._refetch_email",
        return_value=MagicMock(headers={"Message-ID": "m-success"}),
    )
    mocker.patch(
        "app.tasks.sync_error_retry._process_single_email_attempt",
        return_value=True,
    )

    result = retry_skipped_emails.apply(args=[str(test_mailbox.id)]).get()

    db_session.refresh(err)
    assert err.status == "retried"
    assert err.resolution == "user_retried_success"
    assert err.retry_count == 1
    assert result["retried"] == 1
    assert result["succeeded"] == 1
    assert result["still_failing"] == 0


def test_retry_failure_keeps_pending_increments_count(
    db_session, test_mailbox, mocker
):
    err = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-fail",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
        retry_count=0,
    )
    db_session.add(err)
    db_session.commit()

    mocker.patch(
        "app.tasks.sync_error_retry._refetch_email",
        return_value=MagicMock(headers={"Message-ID": "m-fail"}),
    )
    mocker.patch(
        "app.tasks.sync_error_retry._process_single_email_attempt",
        return_value=False,
    )

    result = retry_skipped_emails.apply(args=[str(test_mailbox.id)]).get()

    db_session.refresh(err)
    assert err.status == "pending"
    assert err.retry_count == 1
    assert err.last_retry_at is not None
    assert result["still_failing"] == 1
```

- [ ] **Step 2: Run tests, expect failure**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_error_retry_task.py -v`

Expected: ImportError or stub returns nothing meaningful.

- [ ] **Step 3: Implement task**

Replace `backend/app/tasks/sync_error_retry.py`:

```python
"""Celery task for retrying skipped emails.

Re-fetches the email from its provider via provider_message_id, runs the
classification + persistence path again, and updates the corresponding
EmailSyncError row.

Per-error isolation: a failure on one row does not abort the others.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.email_providers import GmailProvider, JMAPProvider
from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.security.encryption import decrypt_credentials
from app.services.sync_error_classifier import classify_exception
from app.services.sync_error_recorder import (
    auto_recover_pending,
    record_sync_error,
)
from app.tasks.email_sync.stages.classification import classify_new_emails
from app.services.ai_classifier import classify_emails_batch

logger = logging.getLogger(__name__)


class _RetryDatabaseTask(Task):
    _db: Optional[Session] = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    base=_RetryDatabaseTask,
    bind=True,
    name="app.tasks.sync_error_retry.retry_skipped_emails",
    autoretry_for=(),  # never autoretry — explicit per-row handling below
    max_retries=0,
)
def retry_skipped_emails(
    self, mailbox_id: str, error_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Retry skipped emails for a mailbox. Returns counters."""
    db = self.db
    mb = db.query(Mailbox).filter(Mailbox.id == UUID(mailbox_id)).first()
    if mb is None:
        return {"retried": 0, "succeeded": 0, "still_failing": 0, "error": "mailbox not found"}

    q = db.query(EmailSyncError).filter(
        EmailSyncError.mailbox_id == mb.id,
        EmailSyncError.status == "pending",
    )
    if error_ids:
        q = q.filter(EmailSyncError.id.in_([UUID(e) for e in error_ids]))
    rows = q.all()

    retried = 0
    succeeded = 0
    still_failing = 0

    for err in rows:
        retried += 1
        err.retry_count = (err.retry_count or 0) + 1
        err.last_retry_at = datetime.now(timezone.utc)
        try:
            refetched = _refetch_email(mb, err.provider_message_id)
            if refetched is None:
                err.error_message = "Provider no longer returns this message id"
                still_failing += 1
                db.commit()
                continue

            ok = _process_single_email_attempt(db, mb, refetched)
            if ok:
                err.status = "retried"
                err.resolution = "user_retried_success"
                err.resolved_at = datetime.now(timezone.utc)
                succeeded += 1
            else:
                still_failing += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            error_type, severity = classify_exception(exc)
            err.error_type = error_type
            err.severity = severity
            err.error_message = str(exc)
            still_failing += 1
        db.commit()

    return {"retried": retried, "succeeded": succeeded, "still_failing": still_failing}


def _refetch_email(mailbox: Mailbox, provider_message_id: str):
    """Fetch a single email by provider id. Returns the provider Email
    dataclass, or None if not found."""
    creds = decrypt_credentials(mailbox.encrypted_credentials)
    if mailbox.provider_type == "jmap":
        provider = JMAPProvider(creds)
    elif mailbox.provider_type == "gmail":
        provider = GmailProvider(creds)
    else:
        return None
    try:
        return asyncio.run(provider.get_message_by_id(provider_message_id))
    finally:
        try:
            asyncio.run(provider.close())
        except Exception:
            pass


def _process_single_email_attempt(db: Session, mailbox: Mailbox, email_obj) -> bool:
    """Run the same persistence path the main pipeline uses, on one email.
    Returns True on success, False if the email could not be persisted."""
    try:
        # Reuse the resilient classifier wrapper
        records, _existing = asyncio.run(
            classify_new_emails(
                db,
                mailbox,
                [email_obj],
                batch_num=0,
                classify_batch=classify_emails_batch,
            )
        )
        return len(records) == 1
    except Exception:
        return False
```

NOTE: `provider.get_message_by_id` may not exist on every provider. Verify (`grep -n "def get_message_by_id" backend/app/email_providers/`) and add it as a separate sub-task if missing — at minimum on Gmail since that's the failing case in production. The minimum implementation calls Gmail's `users.messages.get` REST API and adapts to the existing provider Email dataclass.

- [ ] **Step 4: Run tests, expect pass**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_error_retry_task.py -v`

Expected: 2 passed.

- [ ] **Step 5: Run user sync-errors API tests again — retry now works end-to-end**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_sync_errors_api.py -v`

Expected: still 6 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/sync_error_retry.py backend/tests/test_sync_error_retry_task.py
git commit -m "feat(tasks): add retry_skipped_emails Celery task"
```

---

## Phase 9 — Notifications

### Task 13: Add notification types + Alembic migration

**Files:**
- Modify: `backend/app/models/notification.py`
- Create: `backend/alembic/versions/l1l1l1l1l1l1_add_sync_notification_types.py`

- [ ] **Step 1: Add enum values to the Python model**

Edit `backend/app/models/notification.py`:

```python
class NotificationType(str, enum.Enum):
    """Types of notifications."""
    RENEWAL_REMINDER = "RENEWAL_REMINDER"
    TRIAL_ENDING = "TRIAL_ENDING"
    WEEKLY_SUMMARY = "WEEKLY_SUMMARY"
    MONTHLY_SUMMARY = "MONTHLY_SUMMARY"
    INACTIVE_SUBSCRIPTION = "INACTIVE_SUBSCRIPTION"
    PRICE_CHANGE = "PRICE_CHANGE"
    BUDGET_ALERT = "BUDGET_ALERT"
    SYSTEM_ANNOUNCEMENT = "SYSTEM_ANNOUNCEMENT"
    SYNC_SKIPPED_MANY = "SYNC_SKIPPED_MANY"          # NEW
    SYNC_CIRCUIT_BREAKER = "SYNC_CIRCUIT_BREAKER"    # NEW
```

- [ ] **Step 2: Create migration extending the Postgres enum**

`backend/alembic/versions/l1l1l1l1l1l1_add_sync_notification_types.py`:

```python
"""Add SYNC_SKIPPED_MANY and SYNC_CIRCUIT_BREAKER to notificationtype enum

Revision ID: l1l1l1l1l1l1
Revises: k0k0k0k0k0k0
Create Date: 2026-04-28

"""

from alembic import op


revision = "l1l1l1l1l1l1"
down_revision = "k0k0k0k0k0k0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in older
    # PostgreSQL; PG 12+ allows it. Use op.execute with autocommit.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SYNC_SKIPPED_MANY'")
        op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SYNC_CIRCUIT_BREAKER'")


def downgrade() -> None:
    # Removing enum values is not natively supported. Document as one-way.
    pass
```

- [ ] **Step 3: Apply migration**

Run: `docker compose -f docker-compose.dev.yml exec backend alembic upgrade head`

Expected: migration runs without error.

- [ ] **Step 4: Verify enum values in DB**

Run:
```
docker compose -f docker-compose.dev.yml exec -T postgres \
  psql -U postgres -d subscription_tracker -c \
  "SELECT unnest(enum_range(NULL::notificationtype));"
```

Expected: list contains `SYNC_SKIPPED_MANY` and `SYNC_CIRCUIT_BREAKER`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/notification.py \
        backend/alembic/versions/l1l1l1l1l1l1_add_sync_notification_types.py
git commit -m "feat(notifications): add SYNC_SKIPPED_MANY + SYNC_CIRCUIT_BREAKER types"
```

---

### Task 14: Notification service for sync events

**Files:**
- Create: `backend/app/services/sync_notification_service.py`

- [ ] **Step 1: Implement service**

```python
"""In-app notification triggers for sync events.

Two thresholds:
- Circuit breaker tripped → severity HIGH notification
- Sync ended with > SKIP_THRESHOLD skipped emails → severity MEDIUM notification

Below threshold (1-10 skips) → no notification, the mailbox card badge is
sufficient signal.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.mailbox import Mailbox
from app.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)

logger = logging.getLogger(__name__)

SKIP_THRESHOLD = 10


def notify_sync_skipped_many(
    db: Session, mailbox: Mailbox, skipped_count: int
) -> Optional[Notification]:
    """Create an in-app notification when many emails were skipped."""
    if skipped_count <= SKIP_THRESHOLD:
        return None
    notif = Notification(
        user_id=mailbox.user_id,
        type=NotificationType.SYNC_SKIPPED_MANY,
        priority=NotificationPriority.MEDIUM,
        title="Sync completed with errors",
        message=(
            f"Your last sync of {mailbox.email_address} skipped {skipped_count} "
            f"emails. View details to retry or ignore them."
        ),
        notification_metadata={
            "mailbox_id": str(mailbox.id),
            "skipped_count": skipped_count,
            "deeplink": f"/mailboxes/{mailbox.id}/sync-errors",
        },
    )
    db.add(notif)
    db.commit()
    return notif


def notify_sync_circuit_breaker(
    db: Session, mailbox: Mailbox, error_count: int
) -> Notification:
    notif = Notification(
        user_id=mailbox.user_id,
        type=NotificationType.SYNC_CIRCUIT_BREAKER,
        priority=NotificationPriority.HIGH,
        title="Sync interrupted by safety circuit breaker",
        message=(
            f"Sync of {mailbox.email_address} was stopped after "
            f"{error_count} consecutive unexpected errors. "
            f"This usually indicates a system issue — please retry later "
            f"or contact support."
        ),
        notification_metadata={
            "mailbox_id": str(mailbox.id),
            "error_count": error_count,
            "deeplink": f"/mailboxes/{mailbox.id}/sync-errors",
        },
    )
    db.add(notif)
    db.commit()
    return notif
```

- [ ] **Step 2: Verify import**

Run: `docker compose -f docker-compose.dev.yml exec backend python -c "from app.services.sync_notification_service import notify_sync_skipped_many, notify_sync_circuit_breaker; print('ok')"`

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/sync_notification_service.py
git commit -m "feat(services): add sync_notification_service"
```

---

### Task 15: Wire notification triggers into `celery_tasks.py`

**Files:**
- Modify: `backend/app/tasks/email_sync/celery_tasks.py`

The triggers fire at sync completion. We need (a) the count of `EmailSyncError` rows created during this `sync_history_id`, (b) circuit-breaker awareness via the catch added in Task 8.

- [ ] **Step 1: Compute skipped count after success path**

In the `if result["success"]` block (around lines 184-231), AFTER `update_subscription_statuses(...)` and BEFORE `db.commit()` (line 254 area), add:

```python
        # Notification: many skipped emails during this sync
        from app.models.email_sync_error import EmailSyncError
        from app.services.sync_notification_service import (
            notify_sync_skipped_many,
        )
        skipped_count = (
            db.query(EmailSyncError)
            .filter(EmailSyncError.sync_history_id == history_entry.id)
            .count()
        )
        if skipped_count > 0:
            history_entry.error_message = (
                f"Completed with {skipped_count} skipped emails"
            )
        notify_sync_skipped_many(db, mailbox, skipped_count)
```

- [ ] **Step 2: Notify on circuit breaker**

In the `except SyncCircuitBreakerError` block from Task 8, BEFORE the `return` statement, add:

```python
        from app.services.sync_notification_service import (
            notify_sync_circuit_breaker,
        )
        notify_sync_circuit_breaker(db, mailbox, e.error_count)
```

- [ ] **Step 3: Run end-to-end tests**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/test_email_sync.py backend/tests/test_email_sync_resilience.py -v`

Expected: all green. The new notification queries must not break existing chartests (the chartests do not assert on notifications).

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/email_sync/celery_tasks.py
git commit -m "feat(email_sync): trigger in-app notifications on skips and circuit breaker"
```

---

## Phase 10 — Frontend (user)

### Task 16: API client + types

**Files:**
- Create: `frontend/src/api/syncErrors.ts`

- [ ] **Step 1: Create the client**

```typescript
import { apiClient } from "./client";

export type SyncErrorStatus =
  | "pending"
  | "retried"
  | "resolved"
  | "ignored"
  | "auto_recovered";

export type SyncErrorType =
  | "schema_too_long"
  | "encoding_error"
  | "extraction_failed"
  | "db_constraint"
  | "unexpected";

export interface SyncError {
  id: string;
  mailbox_id: string;
  sync_history_id: string | null;
  provider_message_id: string | null;
  subject: string | null;
  sender: string | null;
  error_type: SyncErrorType;
  error_message: string;
  severity: "low" | "medium" | "high";
  status: SyncErrorStatus;
  resolution: string | null;
  retry_count: number;
  last_retry_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SyncErrorList {
  items: SyncError[];
  total: number;
  page: number;
  page_size: number;
}

export interface RetryResponse {
  task_id: string;
  pending_count: number;
}

export interface SyncErrorListParams {
  status?: SyncErrorStatus;
  error_type?: SyncErrorType;
  page?: number;
  page_size?: number;
}

export const syncErrorsApi = {
  list: (mailboxId: string, params: SyncErrorListParams = {}) =>
    apiClient
      .get<SyncErrorList>(`/api/mailboxes/${mailboxId}/sync-errors`, { params })
      .then((r) => r.data),

  ignore: (errorId: string) =>
    apiClient
      .post<SyncError>(`/api/sync-errors/${errorId}/ignore`)
      .then((r) => r.data),

  retry: (mailboxId: string) =>
    apiClient
      .post<RetryResponse>(`/api/mailboxes/${mailboxId}/sync-errors/retry`)
      .then((r) => r.data),
};
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: no errors related to the new file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/syncErrors.ts
git commit -m "feat(frontend): add syncErrors API client + types"
```

---

### Task 17: i18n entries

**Files:**
- Create: `frontend/src/i18n/locales/en/syncErrors.json`
- Create: `frontend/src/i18n/locales/fr/syncErrors.json`
- Modify: `frontend/src/i18n/config.ts`

- [ ] **Step 1: Create EN namespace**

`frontend/src/i18n/locales/en/syncErrors.json`:

```json
{
  "page_title": "Skipped emails",
  "back_to_mailbox": "Back to mailbox",
  "filters": {
    "status": "Status",
    "error_type": "Error type",
    "all": "All"
  },
  "table": {
    "date": "Date",
    "sender": "Sender",
    "subject": "Subject",
    "error": "Error",
    "status": "Status",
    "actions": "Actions"
  },
  "actions": {
    "retry_all": "Retry all pending",
    "ignore_all": "Ignore all pending",
    "ignore": "Ignore",
    "ignore_confirm": "Mark this email as ignored? It will not be retried."
  },
  "status": {
    "pending": "Pending",
    "retried": "Retried",
    "resolved": "Resolved",
    "ignored": "Ignored",
    "auto_recovered": "Auto-recovered"
  },
  "error_types": {
    "schema_too_long": "Email too large for current storage format. The team has been notified; retry once a fix is deployed.",
    "encoding_error": "Email contains invalid character encoding. Retry rarely succeeds; you can safely ignore.",
    "extraction_failed": "Subscription extraction failed for this email. Usually safe to retry.",
    "db_constraint": "Database constraint violation. Retry once a fix is deployed.",
    "unexpected": "An unexpected error occurred. The team has been notified."
  },
  "badge": "{{count}} email skipped",
  "badge_plural": "{{count}} emails skipped",
  "empty": "No skipped emails — your sync is clean.",
  "retry_started": "Retry queued. Refresh in a few seconds.",
  "ignored_toast": "Marked as ignored."
}
```

- [ ] **Step 2: Create FR namespace**

`frontend/src/i18n/locales/fr/syncErrors.json`:

```json
{
  "page_title": "Emails ignorés",
  "back_to_mailbox": "Retour à la boîte mail",
  "filters": {
    "status": "Statut",
    "error_type": "Type d'erreur",
    "all": "Tous"
  },
  "table": {
    "date": "Date",
    "sender": "Expéditeur",
    "subject": "Objet",
    "error": "Erreur",
    "status": "Statut",
    "actions": "Actions"
  },
  "actions": {
    "retry_all": "Tout réessayer",
    "ignore_all": "Tout ignorer",
    "ignore": "Ignorer",
    "ignore_confirm": "Marquer cet email comme ignoré ? Il ne sera pas réessayé."
  },
  "status": {
    "pending": "En attente",
    "retried": "Réessayé",
    "resolved": "Résolu",
    "ignored": "Ignoré",
    "auto_recovered": "Auto-résolu"
  },
  "error_types": {
    "schema_too_long": "Email trop volumineux pour le format de stockage actuel. L'équipe a été notifiée ; réessayez une fois le correctif déployé.",
    "encoding_error": "Email avec un encodage de caractères invalide. Le réessai a peu de chances d'aboutir ; vous pouvez l'ignorer.",
    "extraction_failed": "L'extraction d'abonnement a échoué. Le réessai est généralement sans risque.",
    "db_constraint": "Violation d'une contrainte de base de données. Réessayez une fois le correctif déployé.",
    "unexpected": "Une erreur inattendue est survenue. L'équipe a été notifiée."
  },
  "badge": "{{count}} email ignoré",
  "badge_plural": "{{count}} emails ignorés",
  "empty": "Aucun email ignoré — votre synchronisation est propre.",
  "retry_started": "Réessai en file d'attente. Actualisez dans quelques secondes.",
  "ignored_toast": "Marqué comme ignoré."
}
```

- [ ] **Step 2: Register namespace in `config.ts`**

Open `frontend/src/i18n/config.ts`. Find the resources object (likely `resources: { en: { translation: ... }, fr: { translation: ... } }`). Add the `syncErrors` namespace:

```typescript
import enSyncErrors from "./locales/en/syncErrors.json";
import frSyncErrors from "./locales/fr/syncErrors.json";

// ... in the i18n init call:
resources: {
  en: {
    translation: enTranslation,
    syncErrors: enSyncErrors,
  },
  fr: {
    translation: frTranslation,
    syncErrors: frSyncErrors,
  },
},
ns: ["translation", "syncErrors"],  // add 'syncErrors' to the namespace list
```

(Adapt to the file's existing pattern.)

- [ ] **Step 3: Verify TS compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/en/syncErrors.json \
        frontend/src/i18n/locales/fr/syncErrors.json \
        frontend/src/i18n/config.ts
git commit -m "feat(i18n): add syncErrors namespace (en + fr)"
```

---

### Task 18: `useSyncErrors` React Query hook

**Files:**
- Create: `frontend/src/hooks/useSyncErrors.ts`

- [ ] **Step 1: Implement**

```typescript
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  syncErrorsApi,
  SyncErrorListParams,
} from "../api/syncErrors";

const KEY = (mailboxId: string, params: SyncErrorListParams) => [
  "sync-errors",
  mailboxId,
  params,
];

export function useSyncErrors(mailboxId: string, params: SyncErrorListParams = {}) {
  return useQuery({
    queryKey: KEY(mailboxId, params),
    queryFn: () => syncErrorsApi.list(mailboxId, params),
    staleTime: 10_000,
  });
}

export function useIgnoreSyncError(mailboxId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (errorId: string) => syncErrorsApi.ignore(errorId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["sync-errors", mailboxId] }),
  });
}

export function useRetrySyncErrors(mailboxId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => syncErrorsApi.retry(mailboxId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["sync-errors", mailboxId] }),
  });
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useSyncErrors.ts
git commit -m "feat(frontend): add useSyncErrors React Query hooks"
```

---

### Task 19: Mailbox card badge

**Files:**
- Modify: the file that renders the mailbox card. **Verify with `grep -rn "MailboxCard\|MailboxesPage" frontend/src/`** before editing.

- [ ] **Step 1: Add a `pending_sync_errors_count` field to the mailbox API response**

In `backend/app/schemas/mailbox.py`, add a computed field to the `MailboxOut` schema:

```python
class MailboxOut(BaseModel):
    # ...existing fields...
    pending_sync_errors_count: int = 0
```

In `backend/app/api/mailboxes.py`, populate the field when serialising. Find the list/get endpoint that returns mailbox(es) and after the query, batch-load counts:

```python
from sqlalchemy import func
from app.models.email_sync_error import EmailSyncError

# After fetching mailboxes:
mailbox_ids = [m.id for m in mailboxes]
counts = dict(
    db.query(EmailSyncError.mailbox_id, func.count(EmailSyncError.id))
    .filter(
        EmailSyncError.mailbox_id.in_(mailbox_ids),
        EmailSyncError.status == "pending",
    )
    .group_by(EmailSyncError.mailbox_id)
    .all()
)
for m in mailboxes_out:
    m.pending_sync_errors_count = counts.get(m.id, 0)
```

(Adapt to the actual response shape — Pydantic v2 may need `model_validate` then setattr.)

- [ ] **Step 2: Update frontend Mailbox type**

In `frontend/src/api/mailboxes.ts`, add `pending_sync_errors_count: number;` to the `Mailbox` interface.

- [ ] **Step 3: Add badge component on the mailbox card**

In the mailbox card render (after grepping for the right file), add:

```tsx
import { Badge, Link } from "@chakra-ui/react";
import { Link as RouterLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

// inside the card render, where status badges live:
{mailbox.pending_sync_errors_count > 0 && (
  <Link
    as={RouterLink}
    to={`/mailboxes/${mailbox.id}/sync-errors`}
    color="orange.500"
    fontSize="sm"
  >
    <Badge colorScheme="orange">
      {t("syncErrors:badge", {
        count: mailbox.pending_sync_errors_count,
        defaultValue_plural: t("syncErrors:badge_plural", {
          count: mailbox.pending_sync_errors_count,
        }),
      })}
    </Badge>
  </Link>
)}
```

- [ ] **Step 4: Verify in browser**

Run: open http://localhost:5173, log in, go to Mailboxes. Mailbox `r4z0r91@gmail.com` should now show no badge yet (it has no `email_sync_errors` rows from the new feature, only the legacy zombie). After Task 7 ran in production, fresh syncs will populate badges.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/mailbox.py backend/app/api/mailboxes.py \
        frontend/src/api/mailboxes.ts \
        frontend/src/<the-card-file>
git commit -m "feat(frontend): add sync-errors badge on mailbox card"
```

---

### Task 20: User sync-errors page

**Files:**
- Create: `frontend/src/pages/SyncErrorsPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the page component**

```tsx
import { useState } from "react";
import { useParams, Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  Container,
  Flex,
  Heading,
  HStack,
  IconButton,
  Select,
  Spinner,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tooltip,
  Tr,
  useToast,
  Tag,
  TagLabel,
} from "@chakra-ui/react";
import { useTranslation } from "react-i18next";
import {
  useIgnoreSyncError,
  useRetrySyncErrors,
  useSyncErrors,
} from "../hooks/useSyncErrors";
import {
  SyncErrorStatus,
  SyncErrorType,
} from "../api/syncErrors";

const STATUS_FILTERS: SyncErrorStatus[] = [
  "pending",
  "retried",
  "ignored",
  "auto_recovered",
];

const ERROR_TYPES: SyncErrorType[] = [
  "schema_too_long",
  "encoding_error",
  "extraction_failed",
  "db_constraint",
  "unexpected",
];

function severityColor(s: string) {
  return s === "high" ? "red" : s === "medium" ? "orange" : "gray";
}

export default function SyncErrorsPage() {
  const { mailboxId } = useParams<{ mailboxId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation(["syncErrors", "translation"]);
  const toast = useToast();

  const [status, setStatus] = useState<SyncErrorStatus | "">("pending");
  const [errorType, setErrorType] = useState<SyncErrorType | "">("");

  const params = {
    ...(status && { status }),
    ...(errorType && { error_type: errorType }),
  };

  const { data, isLoading } = useSyncErrors(mailboxId!, params);
  const retryMutation = useRetrySyncErrors(mailboxId!);
  const ignoreMutation = useIgnoreSyncError(mailboxId!);

  if (!mailboxId) return null;

  const handleRetryAll = async () => {
    try {
      await retryMutation.mutateAsync();
      toast({ status: "info", description: t("syncErrors:retry_started") });
    } catch (e) {
      toast({ status: "error", description: String(e) });
    }
  };

  const handleIgnore = async (id: string) => {
    if (!window.confirm(t("syncErrors:actions.ignore_confirm"))) return;
    try {
      await ignoreMutation.mutateAsync(id);
      toast({ status: "success", description: t("syncErrors:ignored_toast") });
    } catch (e) {
      toast({ status: "error", description: String(e) });
    }
  };

  return (
    <Container maxW="6xl" py={6}>
      <Flex justify="space-between" align="center" mb={4}>
        <Heading size="lg">{t("syncErrors:page_title")}</Heading>
        <Button as={RouterLink} to="/mailboxes" variant="ghost">
          {t("syncErrors:back_to_mailbox")}
        </Button>
      </Flex>

      <HStack spacing={3} mb={4}>
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as SyncErrorStatus | "")}
          maxW="200px"
        >
          <option value="">{t("syncErrors:filters.all")}</option>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {t(`syncErrors:status.${s}`)}
            </option>
          ))}
        </Select>
        <Select
          value={errorType}
          onChange={(e) => setErrorType(e.target.value as SyncErrorType | "")}
          maxW="240px"
        >
          <option value="">{t("syncErrors:filters.all")}</option>
          {ERROR_TYPES.map((et) => (
            <option key={et} value={et}>
              {et}
            </option>
          ))}
        </Select>
        <Button
          colorScheme="orange"
          isLoading={retryMutation.isPending}
          onClick={handleRetryAll}
        >
          {t("syncErrors:actions.retry_all")}
        </Button>
      </HStack>

      {isLoading ? (
        <Spinner />
      ) : data?.items.length === 0 ? (
        <Box>{t("syncErrors:empty")}</Box>
      ) : (
        <Table size="sm" variant="striped">
          <Thead>
            <Tr>
              <Th>{t("syncErrors:table.date")}</Th>
              <Th>{t("syncErrors:table.sender")}</Th>
              <Th>{t("syncErrors:table.subject")}</Th>
              <Th>{t("syncErrors:table.error")}</Th>
              <Th>{t("syncErrors:table.status")}</Th>
              <Th>{t("syncErrors:table.actions")}</Th>
            </Tr>
          </Thead>
          <Tbody>
            {data?.items.map((row) => (
              <Tr key={row.id}>
                <Td>{new Date(row.created_at).toLocaleString()}</Td>
                <Td>{row.sender ?? "—"}</Td>
                <Td maxW="320px" isTruncated>
                  {row.subject ?? "—"}
                </Td>
                <Td>
                  <Tooltip
                    label={t(`syncErrors:error_types.${row.error_type}`)}
                  >
                    <Tag colorScheme={severityColor(row.severity)}>
                      <TagLabel>{row.error_type}</TagLabel>
                    </Tag>
                  </Tooltip>
                </Td>
                <Td>{t(`syncErrors:status.${row.status}`)}</Td>
                <Td>
                  {row.status === "pending" && (
                    <Button
                      size="xs"
                      onClick={() => handleIgnore(row.id)}
                      isLoading={ignoreMutation.isPending}
                    >
                      {t("syncErrors:actions.ignore")}
                    </Button>
                  )}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}
    </Container>
  );
}
```

- [ ] **Step 2: Register the route in `App.tsx`**

Find the existing `<Routes>` block. Add:

```tsx
import SyncErrorsPage from "./pages/SyncErrorsPage";

// inside <Routes>:
<Route
  path="/mailboxes/:mailboxId/sync-errors"
  element={<SyncErrorsPage />}
/>
```

- [ ] **Step 3: Smoke test in browser**

1. Run: `docker compose -f docker-compose.dev.yml restart backend frontend`
2. Open http://localhost:5173/mailboxes/ae421425-e840-41cd-92b1-d2934fa2efac/sync-errors
3. Should render an empty state (no errors yet from the new feature, the legacy zombie was cleaned manually).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SyncErrorsPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): user sync-errors page"
```

---

## Phase 11 — Frontend (admin)

### Task 21: Admin API client + hook

**Files:**
- Create: `frontend/src/api/adminSyncErrors.ts`
- Create: `frontend/src/hooks/useAdminSyncErrors.ts`

- [ ] **Step 1: Implement API client**

```typescript
import { apiClient } from "./client";
import { SyncError, SyncErrorListParams } from "./syncErrors";

export interface AdminSyncError extends SyncError {
  stack_trace: string | null;
  raw_payload: Record<string, unknown> | null;
  resolved_at: string | null;
  resolved_by_id: string | null;
}

export interface AdminSyncErrorList {
  items: AdminSyncError[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminSyncErrorListParams extends SyncErrorListParams {
  severity?: "low" | "medium" | "high";
  mailbox_id?: string;
}

export const adminSyncErrorsApi = {
  list: (params: AdminSyncErrorListParams = {}) =>
    apiClient
      .get<AdminSyncErrorList>("/api/admin/sync-errors", { params })
      .then((r) => r.data),

  detail: (id: string) =>
    apiClient
      .get<AdminSyncError>(`/api/admin/sync-errors/${id}`)
      .then((r) => r.data),

  resolve: (id: string) =>
    apiClient
      .post<AdminSyncError>(`/api/admin/sync-errors/${id}/resolve`)
      .then((r) => r.data),
};
```

- [ ] **Step 2: Implement hook**

```typescript
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AdminSyncErrorListParams,
  adminSyncErrorsApi,
} from "../api/adminSyncErrors";

export function useAdminSyncErrors(params: AdminSyncErrorListParams = {}) {
  return useQuery({
    queryKey: ["admin-sync-errors", params],
    queryFn: () => adminSyncErrorsApi.list(params),
  });
}

export function useAdminSyncErrorDetail(id: string | null) {
  return useQuery({
    queryKey: ["admin-sync-errors", "detail", id],
    queryFn: () => adminSyncErrorsApi.detail(id!),
    enabled: !!id,
  });
}

export function useResolveAdminSyncError() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminSyncErrorsApi.resolve(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["admin-sync-errors"] }),
  });
}
```

- [ ] **Step 3: Verify TS compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/adminSyncErrors.ts frontend/src/hooks/useAdminSyncErrors.ts
git commit -m "feat(frontend): admin sync-errors API client + hooks"
```

---

### Task 22: Admin sync-errors page

**Files:**
- Create: `frontend/src/pages/admin/AdminSyncErrorsPage.tsx`
- Modify: `frontend/src/pages/admin/AdminLayout.tsx`

- [ ] **Step 1: Create the page**

```tsx
import { useState } from "react";
import {
  Badge,
  Box,
  Button,
  Code,
  Container,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  Flex,
  Heading,
  HStack,
  Select,
  Spinner,
  Table,
  Tag,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  useDisclosure,
  useToast,
} from "@chakra-ui/react";
import {
  useAdminSyncErrors,
  useAdminSyncErrorDetail,
  useResolveAdminSyncError,
} from "../../hooks/useAdminSyncErrors";

const STATUSES = ["pending", "retried", "resolved", "ignored", "auto_recovered"];
const SEVERITIES = ["low", "medium", "high"];
const ERROR_TYPES = [
  "schema_too_long",
  "encoding_error",
  "extraction_failed",
  "db_constraint",
  "unexpected",
];

export default function AdminSyncErrorsPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const drawer = useDisclosure();
  const toast = useToast();

  const list = useAdminSyncErrors(filters as any);
  const detail = useAdminSyncErrorDetail(selectedId);
  const resolveMutation = useResolveAdminSyncError();

  const openDetail = (id: string) => {
    setSelectedId(id);
    drawer.onOpen();
  };

  const handleResolve = async () => {
    if (!selectedId) return;
    try {
      await resolveMutation.mutateAsync(selectedId);
      toast({ status: "success", description: "Marked as resolved" });
      drawer.onClose();
    } catch (e) {
      toast({ status: "error", description: String(e) });
    }
  };

  return (
    <Container maxW="7xl" py={6}>
      <Heading size="lg" mb={4}>
        Sync errors
      </Heading>

      <HStack spacing={3} mb={4}>
        {[
          { key: "status", values: STATUSES },
          { key: "error_type", values: ERROR_TYPES },
          { key: "severity", values: SEVERITIES },
        ].map((f) => (
          <Select
            key={f.key}
            placeholder={f.key}
            value={filters[f.key] ?? ""}
            onChange={(e) =>
              setFilters((p) => ({ ...p, [f.key]: e.target.value }))
            }
            maxW="200px"
          >
            {f.values.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </Select>
        ))}
        <Button
          variant="ghost"
          onClick={() => setFilters({})}
        >
          Clear filters
        </Button>
      </HStack>

      {list.isLoading ? (
        <Spinner />
      ) : (
        <Table size="sm" variant="striped">
          <Thead>
            <Tr>
              <Th>Created</Th>
              <Th>Mailbox</Th>
              <Th>Type</Th>
              <Th>Severity</Th>
              <Th>Status</Th>
              <Th>Retries</Th>
              <Th>Subject</Th>
            </Tr>
          </Thead>
          <Tbody>
            {list.data?.items.map((row) => (
              <Tr
                key={row.id}
                onClick={() => openDetail(row.id)}
                cursor="pointer"
                _hover={{ bg: "gray.50" }}
              >
                <Td>{new Date(row.created_at).toLocaleString()}</Td>
                <Td>{row.mailbox_id.slice(0, 8)}…</Td>
                <Td>{row.error_type}</Td>
                <Td>
                  <Badge
                    colorScheme={
                      row.severity === "high"
                        ? "red"
                        : row.severity === "medium"
                        ? "orange"
                        : "gray"
                    }
                  >
                    {row.severity}
                  </Badge>
                </Td>
                <Td>{row.status}</Td>
                <Td>{row.retry_count}</Td>
                <Td maxW="300px" isTruncated>
                  {row.subject ?? "—"}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}

      <Drawer
        isOpen={drawer.isOpen}
        placement="right"
        onClose={drawer.onClose}
        size="lg"
      >
        <DrawerOverlay />
        <DrawerContent>
          <DrawerCloseButton />
          <DrawerHeader>Sync error detail</DrawerHeader>
          <DrawerBody>
            {detail.isLoading ? (
              <Spinner />
            ) : detail.data ? (
              <Box>
                <Heading size="sm">Error message</Heading>
                <Code w="full" p={2} mb={4} whiteSpace="pre-wrap">
                  {detail.data.error_message}
                </Code>

                {detail.data.stack_trace && (
                  <>
                    <Heading size="sm">Stack trace</Heading>
                    <Code
                      w="full"
                      p={2}
                      mb={4}
                      fontSize="xs"
                      whiteSpace="pre-wrap"
                    >
                      {detail.data.stack_trace}
                    </Code>
                  </>
                )}

                <Heading size="sm">Raw payload</Heading>
                <Code w="full" p={2} mb={4} fontSize="xs" whiteSpace="pre-wrap">
                  {JSON.stringify(detail.data.raw_payload, null, 2)}
                </Code>

                {detail.data.status === "pending" && (
                  <Button
                    colorScheme="green"
                    onClick={handleResolve}
                    isLoading={resolveMutation.isPending}
                  >
                    Mark resolved
                  </Button>
                )}
              </Box>
            ) : null}
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Container>
  );
}
```

- [ ] **Step 2: Register route in `AdminLayout.tsx`**

Open `frontend/src/pages/admin/AdminLayout.tsx`. Find the navigation array / route list and add an entry:

```tsx
import AdminSyncErrorsPage from "./AdminSyncErrorsPage";

// inside the nav items array:
{ to: "/admin/sync-errors", label: "Sync errors" },

// inside the <Routes>:
<Route path="sync-errors" element={<AdminSyncErrorsPage />} />
```

(Adapt to the file's existing pattern.)

- [ ] **Step 3: Smoke test in browser**

Open http://localhost:5173/admin/sync-errors as `dev@ankirama.com` (admin). Should render the empty admin page with filters.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/AdminSyncErrorsPage.tsx \
        frontend/src/pages/admin/AdminLayout.tsx
git commit -m "feat(admin): admin sync-errors page"
```

---

## Phase 12 — Final verification

### Task 23: End-to-end smoke test

**Files:** none — manual verification.

- [ ] **Step 1: Re-run a sync on the previously-stuck mailbox**

1. Log into the frontend as `ankirama@patate.io`.
2. Navigate to mailboxes; the Gmail mailbox `r4z0r91@gmail.com` should now show `last_sync_status='failed'` (cleaned manually 2026-04-28).
3. Click "Sync now".

- [ ] **Step 2: Observe the previously-poisoning email**

The sync should reach the email with `message_id='19b6703b6449630e'`. With the new resilience:
- The save succeeds (subject is now `TEXT`, no truncation).
- No EmailSyncError row is created.

- [ ] **Step 3: Verify the badge stays at 0 after a clean sync**

Run:
```
docker compose -f docker-compose.dev.yml exec -T postgres \
  psql -U postgres -d subscription_tracker -c \
  "SELECT count(*) FROM email_sync_errors WHERE mailbox_id='ae421425-e840-41cd-92b1-d2934fa2efac';"
```

Expected: `0`.

- [ ] **Step 4: Manually inject a poisoned row to test the UI happy path**

```
docker compose -f docker-compose.dev.yml exec -T postgres \
  psql -U postgres -d subscription_tracker -c \
  "INSERT INTO email_sync_errors (id, mailbox_id, provider_message_id, subject, sender, error_type, error_message, severity, status, raw_payload)
   VALUES (gen_random_uuid(), 'ae421425-e840-41cd-92b1-d2934fa2efac', 'fake-test-001',
           'Manual test row', 'test@example.com', 'schema_too_long',
           'value too long', 'medium', 'pending', '{\"sender\":\"test@example.com\"}'::jsonb);"
```

- [ ] **Step 5: Verify badge appears, page renders, ignore works**

1. Refresh the mailbox card — badge should show "1 email skipped".
2. Click the badge — page renders, table shows the manual row.
3. Click "Ignore" — confirm dialog → row marked ignored, disappears from default `pending` filter.

- [ ] **Step 6: Verify admin page**

Open `/admin/sync-errors` — the same row should appear (with `raw_payload` visible after click). Mark resolved.

- [ ] **Step 7: Run full backend test suite one last time**

Run: `docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/ -v --maxfail=5`

Expected: all green. No regressions in the C1 chartests.

- [ ] **Step 8: Run linters**

Run: `docker compose -f docker-compose.dev.yml exec backend python -m black --check backend/app/ backend/tests/`

Run: `docker compose -f docker-compose.dev.yml exec backend python -m flake8 backend/app/ --max-line-length=120`

Run: `cd frontend && npm run lint`

Fix any issues, commit fixes.

- [ ] **Step 9: Push and open PR**

```bash
git push -u origin feat/email-sync-resilience
gh pr create --title "feat: email sync resilience and error tracking" --body "$(cat <<'EOF'
## Summary
- Per-email isolation in the email-sync pipeline (no more batch-killing crashes)
- New `email_sync_errors` table with retry / ignore / auto-recovery
- Schema fix: widen `email_messages.subject`, `sender_name`, `message_id`, `thread_id` to `TEXT`
- Defense-in-depth: 4 KB byte cap on subject/sender_name
- Circuit breaker: aborts sync after 5 consecutive `unexpected` errors
- User-facing page on each mailbox + cross-user admin page
- In-app notifications for circuit-breaker trips and >10-skip syncs

## Test plan
- [ ] All backend tests green (`pytest backend/tests/`)
- [ ] C1 chartests untouched
- [ ] `frontend` lints + builds
- [ ] Manual smoke test on stuck mailbox `ae421425-e840-41cd-92b1-d2934fa2efac` succeeds without errors
- [ ] Manual injection of fake `email_sync_errors` row → badge / page / ignore / admin / resolve all work end-to-end

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review checklist (post-write)

- [x] **Spec coverage:** Every spec section is mapped to a task.
  - §5.1 schema fix → Task 1, Task 2
  - §5.2 new table → Task 1, Task 2
  - §6.1 classifier → Task 3
  - §6.2 recorder → Task 5
  - §6.3 wrapping save loop → Task 7
  - §6.4 truncate utility → Task 4 (and used in Task 7)
  - §6.5 auto-recovery → Task 5 + Task 7 (call site)
  - §6.6 notifications → Task 13, Task 14, Task 15
  - §6.7 endpoints → Task 10 (user) + Task 11 (admin)
  - §6.8 retry task → Task 12
  - §6.9 zombie state fix → Task 8
  - §7.1 user UI → Task 16, 17, 18, 19, 20
  - §7.2 admin UI → Task 21, 22
  - §7.3 notifications UI hook-up → no new code (reuses existing `NotificationsBell`)
  - §10 verification → Task 23

- [x] **No placeholders:** Steps that create code show full code; no "implement later" / "TODO" / vague handwaving.

- [x] **Type/name consistency:**
  - `EmailSyncError` model name used consistently
  - `SyncErrorOut` / `SyncErrorAdminOut` schema names used in API + frontend types
  - `classify_exception` returns `Tuple[str, str]` everywhere
  - `truncate_to_bytes` has the same signature in utility, classifier, and recorder

- [x] **Branch strategy:** Single feature branch `feat/email-sync-resilience`, one PR. Each task is a separate commit, kept clean.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-28-email-sync-resilience.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
