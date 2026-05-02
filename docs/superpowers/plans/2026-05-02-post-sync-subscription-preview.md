# Post-sync Subscription Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every automated sync, surface the subscriptions it just created or updated in a right-side drawer accessible from an in-app notification or a "View" link on the mailbox card.

**Architecture:** New `discovered_via_sync_history_id` FK on `subscriptions`, `sync_history_id` FK on `price_history`, `last_sync_history_id` mirror on `mailboxes`. New API endpoint `/api/sync-history/{id}/preview` reads the per-run scope. New `SYNC_PREVIEW_AVAILABLE` notification type; payload's `notification_metadata.sync_history_id` powers the front-end click. Frontend Chakra `Drawer` with two sections (New / Updated), confidence-bucket badges derived from `subscription.confidence_score`.

**Tech Stack:** SQLAlchemy 2.0, Alembic, FastAPI, Pydantic v2, React 18 + TypeScript, Chakra UI v2, React Query v5, i18next.

**Spec:** `docs/superpowers/specs/2026-05-02-post-sync-subscription-preview-design.md`

---

## File Structure

**Backend — create:**
- `backend/alembic/versions/o4o4o4o4o4o4_add_sync_preview_links.py` — migration for the 3 new FKs.
- `backend/alembic/versions/p5p5p5p5p5p5_add_sync_preview_notif_type.py` — migration for the new enum value.
- `backend/app/api/sync_preview.py` — single FastAPI router for `GET /api/sync-history/{id}/preview`.
- `backend/app/schemas/sync_preview.py` — Pydantic schemas for the response shape.
- `backend/tests/test_sync_preview_api.py` — endpoint integration tests.

**Backend — modify:**
- `backend/app/models/subscription.py` — add `discovered_via_sync_history_id` Column + relationship.
- `backend/app/models/price_history.py` — add `sync_history_id` Column.
- `backend/app/models/mailbox.py` — add `last_sync_history_id` Column.
- `backend/app/models/notification.py` — add `SYNC_PREVIEW_AVAILABLE` enum value.
- `backend/app/tasks/email_sync/stages/persistence.py` — set `discovered_via_sync_history_id` on INSERT, `sync_history_id` on price_history INSERT. Needs `sync_history` threaded into the call.
- `backend/app/tasks/email_sync/celery_tasks.py` — pass `history_entry` into the persistence stage and mirror `last_sync_history_id` onto the mailbox at completion; trigger notification.
- `backend/app/tasks/email_sync/orchestrator.py` — thread `sync_history` from `_sync_mailbox_async` into the persistence stage.
- `backend/app/services/sync_notification_service.py` — add `notify_sync_preview_available`.
- `backend/app/main.py` — register the new sync_preview router.

**Frontend — create:**
- `frontend/src/api/syncPreview.ts` — API client + types.
- `frontend/src/hooks/useSyncPreview.ts` — React Query hook.
- `frontend/src/components/mailboxes/SyncPreviewDrawer.tsx` — the drawer component.
- `frontend/src/i18n/locales/en/syncPreview.json`
- `frontend/src/i18n/locales/fr/syncPreview.json`

**Frontend — modify:**
- `frontend/src/types/index.ts` — extend `Mailbox` with `last_sync_history_id`.
- `frontend/src/i18n/config.ts` — register `syncPreview` namespace.
- `frontend/src/components/mailboxes/MailboxesPage.tsx` — add "View" link next to "New This Run" + drawer state.
- `frontend/src/components/notifications/NotificationListPage.tsx` — add type icon, label, and click handler for `sync_preview_available`.

---

## Task 1: Backend migration + model columns

**Files:**
- Create: `backend/alembic/versions/o4o4o4o4o4o4_add_sync_preview_links.py`
- Modify: `backend/app/models/subscription.py`
- Modify: `backend/app/models/price_history.py`
- Modify: `backend/app/models/mailbox.py`

- [ ] **Step 1: Create the Alembic migration**

```python
"""Add sync_history_id links on subscriptions / price_history / mailboxes

Revision ID: o4o4o4o4o4o4
Revises: n3n3n3n3n3n3
Create Date: 2026-05-02

"""

from alembic import op
import sqlalchemy as sa


revision = "o4o4o4o4o4o4"
down_revision = "n3n3n3n3n3n3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column(
            "discovered_via_sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_subscriptions_discovered_via_sync_history_id",
        "subscriptions",
        ["discovered_via_sync_history_id"],
    )
    op.add_column(
        "price_history",
        sa.Column(
            "sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_price_history_sync_history_id",
        "price_history",
        ["sync_history_id"],
    )
    op.add_column(
        "mailboxes",
        sa.Column(
            "last_sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("mailboxes", "last_sync_history_id")
    op.drop_index("ix_price_history_sync_history_id", "price_history")
    op.drop_column("price_history", "sync_history_id")
    op.drop_index("ix_subscriptions_discovered_via_sync_history_id", "subscriptions")
    op.drop_column("subscriptions", "discovered_via_sync_history_id")
```

- [ ] **Step 2: Run the migration**

```bash
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

Expected: `Running upgrade n3n3n3n3n3n3 -> o4o4o4o4o4o4`.

- [ ] **Step 3: Add the column to `subscriptions` model**

In `backend/app/models/subscription.py`, find the section near `mailbox_id` (around line 42) and add after the existing FK columns:

```python
discovered_via_sync_history_id = Column(
    UUID(as_uuid=True),
    ForeignKey("sync_history.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```

- [ ] **Step 4: Add the column to `price_history` model**

In `backend/app/models/price_history.py`, after the existing `subscription_id` FK column:

```python
sync_history_id = Column(
    UUID(as_uuid=True),
    ForeignKey("sync_history.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```

- [ ] **Step 5: Add the column to `mailbox` model**

In `backend/app/models/mailbox.py`, in the "Sync status" block (after `last_sync_new_emails_count`):

```python
last_sync_history_id = Column(
    UUID(as_uuid=True),
    ForeignKey("sync_history.id", ondelete="SET NULL"),
    nullable=True,
)
```

- [ ] **Step 6: Verify backend boots**

```bash
docker-compose -f docker-compose.dev.yml restart backend
sleep 4
docker-compose -f docker-compose.dev.yml logs --tail=20 backend | grep -E "Application startup complete|Error"
```

Expected: `Application startup complete.`, no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/o4o4o4o4o4o4_add_sync_preview_links.py backend/app/models/subscription.py backend/app/models/price_history.py backend/app/models/mailbox.py
git commit -m "feat(models): add sync_history_id FKs for post-sync preview"
```

---

## Task 2: Wire sync_history_id at persistence stage

**Files:**
- Modify: `backend/app/tasks/email_sync/stages/persistence.py`
- Modify: `backend/app/tasks/email_sync/orchestrator.py` (thread sync_history through if not already)

- [ ] **Step 1: Inspect orchestrator → persistence call signature**

```bash
grep -n "persistence\|process_subscription\|sync_history\|history_entry" backend/app/tasks/email_sync/orchestrator.py | head -20
grep -n "def " backend/app/tasks/email_sync/stages/persistence.py | head -10
```

Expected: identify which function in `persistence.py` does the `db.add(Subscription(...))` and the `db.add(PriceHistory(...))`, and how it's called from the orchestrator. The `history_entry` (a `SyncHistory` instance) is already created in `celery_tasks.py:150` and passed into `_sync_mailbox_async`.

- [ ] **Step 2: Thread `history_entry` (or just its `id`) into the persistence call**

Add a kwarg `sync_history_id: UUID | None = None` to the persistence-stage entrypoint(s). In the orchestrator, pass `sync_history_id=history_entry.id` when calling it. This is a mechanical signature change — preserve all existing args.

- [ ] **Step 3: Set the column when creating a new Subscription**

Find every `Subscription(...)` constructor call inside `persistence.py` and add `discovered_via_sync_history_id=sync_history_id` to its kwargs. Do not modify subscription updates — only fresh inserts.

Search hint:

```bash
grep -nE "Subscription\(" backend/app/tasks/email_sync/stages/persistence.py
```

- [ ] **Step 4: Set the column when creating a new PriceHistory row**

Find the `PriceHistory(...)` constructor call(s) (around line 113-130 per the file map in the spec) and add `sync_history_id=sync_history_id`.

- [ ] **Step 5: Restart and run sync-related tests**

```bash
docker-compose -f docker-compose.dev.yml restart backend
docker-compose -f docker-compose.dev.yml exec -T backend python -m pytest tests/ -k "sync or persistence" --tb=short -q | tail -10
```

Expected: 184/185 tests pass (same baseline failure on `test_create_mailbox_connection_test_fails`). No new failures.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/email_sync/stages/persistence.py backend/app/tasks/email_sync/orchestrator.py
git commit -m "feat(email_sync): tag created subscriptions and price changes with sync_history_id"
```

---

## Task 3: Mirror last_sync_history_id at sync completion

**Files:**
- Modify: `backend/app/tasks/email_sync/celery_tasks.py`

- [ ] **Step 1: Add the mirror assignment**

In `celery_tasks.py`, find the block that already populates `mailbox.last_sync_oldest_email_date` etc. (the metrics block right before `db.commit()` near line 290). Add at the end of that block, before the commit:

```python
mailbox.last_sync_history_id = history_entry.id
```

- [ ] **Step 2: Verify**

```bash
docker-compose -f docker-compose.dev.yml restart backend celery_worker
docker-compose -f docker-compose.dev.yml exec -T backend python -m pytest tests/ -k "sync" --tb=short -q | tail -5
```

Expected: same baseline (184 pass, 1 known fail).

- [ ] **Step 3: Commit**

```bash
git add backend/app/tasks/email_sync/celery_tasks.py
git commit -m "feat(email_sync): mirror sync_history_id onto mailbox at completion"
```

---

## Task 4: Pydantic schemas for the preview response

**Files:**
- Create: `backend/app/schemas/sync_preview.py`

- [ ] **Step 1: Create the schemas file**

```python
"""Pydantic schemas for the post-sync subscription preview."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncPreviewMeta(BaseModel):
    id: UUID
    mailbox_id: UUID
    mailbox_email: str
    started_at: datetime
    completed_at: Optional[datetime]
    new_emails_count: Optional[int]


class NewSubscriptionPreview(BaseModel):
    id: UUID
    provider: str
    custom_label: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str
    billing_cycle: str
    category: Optional[str] = None
    confidence_bucket: Literal["auto_saved", "pending_review"]
    source_email_subject: Optional[str] = None
    source_email_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UpdatedSubscriptionPreview(BaseModel):
    id: UUID
    provider: str
    update_type: Literal["price_change", "cancellation_detected"]
    before: dict[str, Any]
    after: dict[str, Any]
    source_email_subject: Optional[str] = None
    source_email_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SyncPreviewResponse(BaseModel):
    sync_history: SyncPreviewMeta
    new_subscriptions: list[NewSubscriptionPreview]
    updated_subscriptions: list[UpdatedSubscriptionPreview]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/sync_preview.py
git commit -m "feat(schemas): add sync preview response schemas"
```

---

## Task 5: Sync preview API endpoint + auth + handler

**Files:**
- Create: `backend/app/api/sync_preview.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_sync_preview_api.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_sync_preview_api.py`:

```python
"""Integration tests for GET /api/sync-history/{id}/preview."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.sync_history import SyncHistory


def _make_sync_history(db, mailbox_id):
    sh = SyncHistory(
        mailbox_id=mailbox_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status="completed",
        total_emails_processed=2,
        new_emails_count=2,
    )
    db.add(sh)
    db.commit()
    db.refresh(sh)
    return sh


class TestSyncPreviewEndpoint:
    def test_returns_404_for_unknown_id(self, client: TestClient, auth_headers):
        unknown = uuid4()
        r = client.get(f"/api/sync-history/{unknown}/preview", headers=auth_headers)
        assert r.status_code == 404

    def test_returns_404_when_sync_history_belongs_to_other_user(
        self, client: TestClient, db, other_user_mailbox, auth_headers
    ):
        sh = _make_sync_history(db, other_user_mailbox.id)
        r = client.get(f"/api/sync-history/{sh.id}/preview", headers=auth_headers)
        assert r.status_code == 404

    def test_buckets_subscription_by_confidence(
        self, client: TestClient, db, user_mailbox, auth_headers
    ):
        sh = _make_sync_history(db, user_mailbox.id)
        auto = Subscription(
            mailbox_id=user_mailbox.id,
            user_id=user_mailbox.user_id,
            provider="Netflix",
            amount=Decimal("14.99"),
            currency="EUR",
            billing_cycle="monthly",
            confidence_score=Decimal("92.0"),
            discovered_via_sync_history_id=sh.id,
        )
        review = Subscription(
            mailbox_id=user_mailbox.id,
            user_id=user_mailbox.user_id,
            provider="Patreon",
            amount=Decimal("5.00"),
            currency="EUR",
            billing_cycle="monthly",
            confidence_score=Decimal("70.0"),
            discovered_via_sync_history_id=sh.id,
        )
        db.add_all([auto, review])
        db.commit()

        r = client.get(f"/api/sync-history/{sh.id}/preview", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        buckets = {row["provider"]: row["confidence_bucket"] for row in body["new_subscriptions"]}
        assert buckets == {"Netflix": "auto_saved", "Patreon": "pending_review"}

    def test_returns_empty_arrays_when_run_produced_nothing(
        self, client: TestClient, db, user_mailbox, auth_headers
    ):
        sh = _make_sync_history(db, user_mailbox.id)
        r = client.get(f"/api/sync-history/{sh.id}/preview", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["new_subscriptions"] == []
        assert body["updated_subscriptions"] == []
        assert body["sync_history"]["id"] == str(sh.id)
```

The plan assumes existing fixtures (`client`, `auth_headers`, `db`, `user_mailbox`, `other_user_mailbox`). Check `backend/tests/conftest.py` first; reuse what exists, add fixtures only if missing.

- [ ] **Step 2: Run tests to verify they fail with "endpoint not found"**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m pytest tests/test_sync_preview_api.py -v | tail -10
```

Expected: 4 tests FAIL with 404 / collection errors due to missing endpoint.

- [ ] **Step 3: Create the router**

Create `backend/app/api/sync_preview.py`:

```python
"""GET /api/sync-history/{id}/preview — read-only preview of one sync run."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.email_message import EmailMessage, subscription_emails
from app.models.mailbox import Mailbox
from app.models.price_history import PriceHistory
from app.models.subscription import Subscription
from app.models.sync_history import SyncHistory
from app.models.user import User
from app.schemas.sync_preview import (
    NewSubscriptionPreview,
    SyncPreviewMeta,
    SyncPreviewResponse,
    UpdatedSubscriptionPreview,
)
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/api/sync-history", tags=["sync-preview"])

CONFIDENCE_AUTO_SAVED_THRESHOLD = Decimal("85.0")


def _bucket_for_confidence(score: Decimal | None) -> str:
    if score is not None and score >= CONFIDENCE_AUTO_SAVED_THRESHOLD:
        return "auto_saved"
    return "pending_review"


def _source_email_for_subscription(
    db: Session, subscription_id: UUID, role: str
) -> EmailMessage | None:
    return (
        db.query(EmailMessage)
        .join(
            subscription_emails,
            subscription_emails.c.email_id == EmailMessage.id,
        )
        .filter(
            subscription_emails.c.subscription_id == subscription_id,
            subscription_emails.c.extraction_role == role,
        )
        .order_by(EmailMessage.date.desc())
        .first()
    )


@router.get("/{sync_history_id}/preview", response_model=SyncPreviewResponse)
def get_sync_preview(
    sync_history_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncPreviewResponse:
    sh = (
        db.query(SyncHistory)
        .join(Mailbox, Mailbox.id == SyncHistory.mailbox_id)
        .filter(
            SyncHistory.id == sync_history_id,
            Mailbox.user_id == current_user.id,
        )
        .options(joinedload(SyncHistory.mailbox))
        .first()
    )
    if not sh:
        raise HTTPException(status_code=404, detail="Sync history not found")

    new_rows = (
        db.query(Subscription)
        .filter(Subscription.discovered_via_sync_history_id == sync_history_id)
        .all()
    )
    new_subscriptions = []
    for sub in new_rows:
        src = _source_email_for_subscription(db, sub.id, "initial_detection")
        new_subscriptions.append(
            NewSubscriptionPreview(
                id=sub.id,
                provider=sub.provider,
                custom_label=sub.custom_label,
                amount=sub.amount,
                currency=sub.currency,
                billing_cycle=sub.billing_cycle,
                category=getattr(sub.category, "name", None) if getattr(sub, "category_id", None) else None,
                confidence_bucket=_bucket_for_confidence(sub.confidence_score),
                source_email_subject=src.subject if src else None,
                source_email_date=src.date if src else None,
            )
        )

    price_rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.sync_history_id == sync_history_id)
        .all()
    )
    updated_subscriptions = []
    for ph in price_rows:
        sub = db.query(Subscription).filter(Subscription.id == ph.subscription_id).first()
        if sub is None:
            continue
        src = _source_email_for_subscription(db, sub.id, "price_update")
        updated_subscriptions.append(
            UpdatedSubscriptionPreview(
                id=sub.id,
                provider=sub.provider,
                update_type="price_change",
                before={"amount": float(ph.old_amount) if ph.old_amount is not None else None},
                after={"amount": float(ph.new_amount)},
                source_email_subject=src.subject if src else None,
                source_email_date=src.date if src else None,
            )
        )

    return SyncPreviewResponse(
        sync_history=SyncPreviewMeta(
            id=sh.id,
            mailbox_id=sh.mailbox_id,
            mailbox_email=sh.mailbox.email_address,
            started_at=sh.started_at,
            completed_at=sh.completed_at,
            new_emails_count=sh.new_emails_count,
        ),
        new_subscriptions=new_subscriptions,
        updated_subscriptions=updated_subscriptions,
    )
```

- [ ] **Step 4: Register the router in main.py**

In `backend/app/main.py`, find the existing `app.include_router(...)` block (where other API routers are registered) and add:

```python
from app.api import sync_preview as sync_preview_api
app.include_router(sync_preview_api.router)
```

- [ ] **Step 5: Restart backend, run the tests**

```bash
docker-compose -f docker-compose.dev.yml restart backend
sleep 4
docker-compose -f docker-compose.dev.yml exec -T backend python -m pytest tests/test_sync_preview_api.py -v | tail -10
```

Expected: 4 tests PASS.

- [ ] **Step 6: Run full suite to confirm no regression**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m pytest tests/ -k "sync or mailbox or subscription" --tb=short -q | tail -5
```

Expected: same baseline (1 known fail, all others pass).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/sync_preview.py backend/app/main.py backend/tests/test_sync_preview_api.py
git commit -m "feat(api): add GET /api/sync-history/{id}/preview"
```

---

## Task 6: SYNC_PREVIEW_AVAILABLE notification type + service + trigger

**Files:**
- Create: `backend/alembic/versions/p5p5p5p5p5p5_add_sync_preview_notif_type.py`
- Modify: `backend/app/models/notification.py`
- Modify: `backend/app/services/sync_notification_service.py`
- Modify: `backend/app/tasks/email_sync/celery_tasks.py`

- [ ] **Step 1: Create the enum migration**

```python
"""Add SYNC_PREVIEW_AVAILABLE to notificationtype enum

Revision ID: p5p5p5p5p5p5
Revises: o4o4o4o4o4o4
Create Date: 2026-05-02

"""

from alembic import op


revision = "p5p5p5p5p5p5"
down_revision = "o4o4o4o4o4o4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SYNC_PREVIEW_AVAILABLE'"
        )


def downgrade() -> None:
    pass  # one-way: PG cannot remove enum values
```

- [ ] **Step 2: Apply migration**

```bash
docker-compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

Expected: `Running upgrade o4o4o4o4o4o4 -> p5p5p5p5p5p5`.

- [ ] **Step 3: Add the enum value in Python**

In `backend/app/models/notification.py`, find the `NotificationType` enum and add a member:

```python
SYNC_PREVIEW_AVAILABLE = "sync_preview_available"
```

Place it next to the existing `SYNC_SKIPPED_MANY` / `SYNC_CIRCUIT_BREAKER` members.

- [ ] **Step 4: Add the service helper**

In `backend/app/services/sync_notification_service.py`, mirror the existing `notify_sync_skipped_many` pattern. Add:

```python
def notify_sync_preview_available(
    db: Session,
    user_id: UUID,
    mailbox_id: UUID,
    sync_history_id: UUID,
    new_count: int,
    updated_count: int,
) -> None:
    """Create a low-priority notification when a sync produced new or updated subscriptions."""
    notification = Notification(
        user_id=user_id,
        type=NotificationType.SYNC_PREVIEW_AVAILABLE,
        priority=NotificationPriority.LOW,
        title="Sync preview ready",
        message=f"{new_count} new, {updated_count} updated",
        notification_metadata={
            "sync_history_id": str(sync_history_id),
            "mailbox_id": str(mailbox_id),
            "new_count": new_count,
            "updated_count": updated_count,
        },
    )
    db.add(notification)
    db.commit()
```

Update the imports at the top of the file if needed (`UUID`, `Session`, `Notification`, `NotificationType`, `NotificationPriority` should already be imported by neighbours).

- [ ] **Step 5: Trigger from celery_tasks**

In `celery_tasks.py`, find the existing block where `notify_sync_skipped_many` is called (near line 245). After it, in the same success branch and after the run-scoped metrics have been computed, add:

```python
from app.services.sync_notification_service import (
    notify_sync_preview_available,
)
from app.models.subscription import Subscription
from app.models.price_history import PriceHistory

new_subs_count = (
    db.query(func.count(Subscription.id))
    .filter(Subscription.discovered_via_sync_history_id == history_entry.id)
    .scalar() or 0
)
updated_subs_count = (
    db.query(func.count(PriceHistory.id))
    .filter(PriceHistory.sync_history_id == history_entry.id)
    .scalar() or 0
)
if new_subs_count + updated_subs_count > 0:
    notify_sync_preview_available(
        db,
        user_id=mailbox.user_id,
        mailbox_id=mailbox.id,
        sync_history_id=history_entry.id,
        new_count=new_subs_count,
        updated_count=updated_subs_count,
    )
```

- [ ] **Step 6: Restart and run sync tests**

```bash
docker-compose -f docker-compose.dev.yml restart backend celery_worker
docker-compose -f docker-compose.dev.yml exec -T backend python -m pytest tests/ -k "sync or notification" --tb=short -q | tail -10
```

Expected: same baseline pass count.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/p5p5p5p5p5p5_add_sync_preview_notif_type.py backend/app/models/notification.py backend/app/services/sync_notification_service.py backend/app/tasks/email_sync/celery_tasks.py
git commit -m "feat(notifications): add SYNC_PREVIEW_AVAILABLE type + sync trigger"
```

---

## Task 7: Frontend types, API client, hook, i18n setup

**Files:**
- Create: `frontend/src/api/syncPreview.ts`
- Create: `frontend/src/hooks/useSyncPreview.ts`
- Create: `frontend/src/i18n/locales/en/syncPreview.json`
- Create: `frontend/src/i18n/locales/fr/syncPreview.json`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/i18n/config.ts`

- [ ] **Step 1: Add `last_sync_history_id` to the Mailbox type**

In `frontend/src/types/index.ts`, in the `Mailbox` interface (next to `last_sync_new_emails_count`):

```ts
last_sync_history_id: string | null
```

- [ ] **Step 2: Create the API client**

`frontend/src/api/syncPreview.ts`:

```ts
import apiClient from './client'

export type ConfidenceBucket = 'auto_saved' | 'pending_review'
export type UpdateType = 'price_change' | 'cancellation_detected'

export interface NewSubscriptionPreview {
  id: string
  provider: string
  custom_label: string | null
  amount: number | null
  currency: string
  billing_cycle: string
  category: string | null
  confidence_bucket: ConfidenceBucket
  source_email_subject: string | null
  source_email_date: string | null
}

export interface UpdatedSubscriptionPreview {
  id: string
  provider: string
  update_type: UpdateType
  before: Record<string, unknown>
  after: Record<string, unknown>
  source_email_subject: string | null
  source_email_date: string | null
}

export interface SyncPreviewMeta {
  id: string
  mailbox_id: string
  mailbox_email: string
  started_at: string
  completed_at: string | null
  new_emails_count: number | null
}

export interface SyncPreviewResponse {
  sync_history: SyncPreviewMeta
  new_subscriptions: NewSubscriptionPreview[]
  updated_subscriptions: UpdatedSubscriptionPreview[]
}

export const syncPreviewAPI = {
  get: async (syncHistoryId: string): Promise<SyncPreviewResponse> => {
    const response = await apiClient.get<SyncPreviewResponse>(
      `/sync-history/${syncHistoryId}/preview`,
    )
    return response.data
  },
}
```

- [ ] **Step 3: Create the React Query hook**

`frontend/src/hooks/useSyncPreview.ts`:

```ts
import { useQuery } from '@tanstack/react-query'
import { syncPreviewAPI } from '../api/syncPreview'

export function useSyncPreview(syncHistoryId: string | null) {
  return useQuery({
    queryKey: ['sync-preview', syncHistoryId],
    queryFn: () => syncPreviewAPI.get(syncHistoryId ?? ''),
    enabled: !!syncHistoryId,
    staleTime: 60_000,
  })
}
```

- [ ] **Step 4: Create the i18n files**

`frontend/src/i18n/locales/en/syncPreview.json`:

```json
{
  "drawer_title": "Sync preview",
  "subtitle": "{{mailboxEmail}} — completed {{when}}",
  "section_new": "New subscriptions",
  "section_updated": "Updated subscriptions",
  "badge_auto_saved": "Auto-saved",
  "badge_pending_review": "Pending review",
  "update_price_change": "Price changed: {{before}} → {{after}}",
  "update_cancellation": "Cancellation detected",
  "empty": "Nothing new this run.",
  "view_link": "View",
  "open_subscription": "Open",
  "loading": "Loading preview…"
}
```

`frontend/src/i18n/locales/fr/syncPreview.json`:

```json
{
  "drawer_title": "Aperçu de la synchronisation",
  "subtitle": "{{mailboxEmail}} — terminé le {{when}}",
  "section_new": "Nouveaux abonnements",
  "section_updated": "Abonnements mis à jour",
  "badge_auto_saved": "Sauvegardé auto",
  "badge_pending_review": "À vérifier",
  "update_price_change": "Prix modifié : {{before}} → {{after}}",
  "update_cancellation": "Annulation détectée",
  "empty": "Rien de neuf pour cette synchronisation.",
  "view_link": "Voir",
  "open_subscription": "Ouvrir",
  "loading": "Chargement…"
}
```

- [ ] **Step 5: Register the namespace**

In `frontend/src/i18n/config.ts`, mirror the existing `syncErrors` registration:

```ts
import enSyncPreview from './locales/en/syncPreview.json'
import frSyncPreview from './locales/fr/syncPreview.json'
```

In the `resources` object's `en` and `fr` blocks, add `syncPreview: enSyncPreview` / `syncPreview: frSyncPreview`. In the `ns` array, add `'syncPreview'`.

- [ ] **Step 6: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/syncPreview.ts frontend/src/hooks/useSyncPreview.ts frontend/src/i18n/locales/en/syncPreview.json frontend/src/i18n/locales/fr/syncPreview.json frontend/src/i18n/config.ts frontend/src/types/index.ts
git commit -m "feat(frontend): sync preview API client + hook + i18n + Mailbox type"
```

---

## Task 8: SyncPreviewDrawer component

**Files:**
- Create: `frontend/src/components/mailboxes/SyncPreviewDrawer.tsx`

- [ ] **Step 1: Create the component**

`frontend/src/components/mailboxes/SyncPreviewDrawer.tsx`:

```tsx
import {
  Badge,
  Box,
  Card,
  CardBody,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  Flex,
  Heading,
  HStack,
  Spinner,
  Stack,
  Tag,
  Text,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useSyncPreview } from '../../hooks/useSyncPreview'
import {
  ConfidenceBucket,
  NewSubscriptionPreview,
  UpdatedSubscriptionPreview,
} from '../../api/syncPreview'

interface Props {
  syncHistoryId: string | null
  isOpen: boolean
  onClose: () => void
}

const bucketColor = (bucket: ConfidenceBucket): string =>
  bucket === 'auto_saved' ? 'green' : 'orange'

const formatAmount = (value: unknown, currency: string): string => {
  if (typeof value !== 'number') return '—'
  return `${value.toFixed(2)} ${currency}`
}

export const SyncPreviewDrawer = ({ syncHistoryId, isOpen, onClose }: Props) => {
  const { t } = useTranslation(['syncPreview'])
  const navigate = useNavigate()
  const { data, isLoading } = useSyncPreview(syncHistoryId)

  const goToSubscription = (id: string) => {
    onClose()
    navigate(`/subscriptions/${id}`)
  }

  const renderNewCard = (row: NewSubscriptionPreview) => (
    <Card
      key={row.id}
      cursor="pointer"
      _hover={{ bg: 'blackAlpha.50' }}
      onClick={() => goToSubscription(row.id)}
      size="sm"
    >
      <CardBody>
        <Flex justify="space-between" align="start">
          <Box>
            <Text fontWeight="semibold">
              {row.provider}
              {row.custom_label ? ` — ${row.custom_label}` : ''}
            </Text>
            <Text fontSize="sm" color="gray.600">
              {formatAmount(row.amount, row.currency)} · {row.billing_cycle}
              {row.category ? ` · ${row.category}` : ''}
            </Text>
            {row.source_email_subject && (
              <Text fontSize="xs" color="gray.500" mt={1} noOfLines={1}>
                {row.source_email_subject}
              </Text>
            )}
          </Box>
          <Badge colorScheme={bucketColor(row.confidence_bucket)}>
            {t(`syncPreview:badge_${row.confidence_bucket}`)}
          </Badge>
        </Flex>
      </CardBody>
    </Card>
  )

  const renderUpdatedCard = (row: UpdatedSubscriptionPreview) => {
    const changeText =
      row.update_type === 'price_change'
        ? t('syncPreview:update_price_change', {
            before: row.before.amount ?? '—',
            after: row.after.amount ?? '—',
          })
        : t('syncPreview:update_cancellation')
    return (
      <Card
        key={row.id}
        cursor="pointer"
        _hover={{ bg: 'blackAlpha.50' }}
        onClick={() => goToSubscription(row.id)}
        size="sm"
      >
        <CardBody>
          <Text fontWeight="semibold">{row.provider}</Text>
          <Text fontSize="sm" color="orange.700">
            {changeText}
          </Text>
          {row.source_email_subject && (
            <Text fontSize="xs" color="gray.500" mt={1} noOfLines={1}>
              {row.source_email_subject}
            </Text>
          )}
        </CardBody>
      </Card>
    )
  }

  const subtitle = data
    ? t('syncPreview:subtitle', {
        mailboxEmail: data.sync_history.mailbox_email,
        when: data.sync_history.completed_at
          ? new Date(data.sync_history.completed_at).toLocaleString()
          : '—',
      })
    : ''

  const isEmpty =
    !!data &&
    data.new_subscriptions.length === 0 &&
    data.updated_subscriptions.length === 0

  return (
    <Drawer isOpen={isOpen} placement="right" size="lg" onClose={onClose}>
      <DrawerOverlay />
      <DrawerContent>
        <DrawerCloseButton />
        <DrawerHeader>
          <Heading size="md">{t('syncPreview:drawer_title')}</Heading>
          <Text fontSize="sm" color="gray.600" fontWeight="normal">
            {subtitle}
          </Text>
        </DrawerHeader>
        <DrawerBody>
          {isLoading || !data ? (
            <Flex justify="center" py={8}>
              <Spinner />
            </Flex>
          ) : isEmpty ? (
            <Text color="gray.500">{t('syncPreview:empty')}</Text>
          ) : (
            <Stack spacing={6}>
              {data.new_subscriptions.length > 0 && (
                <Box>
                  <HStack mb={3}>
                    <Heading size="sm">{t('syncPreview:section_new')}</Heading>
                    <Tag colorScheme="green">+{data.new_subscriptions.length}</Tag>
                  </HStack>
                  <Stack spacing={2}>
                    {data.new_subscriptions.map(renderNewCard)}
                  </Stack>
                </Box>
              )}
              {data.updated_subscriptions.length > 0 && (
                <Box>
                  <HStack mb={3}>
                    <Heading size="sm">{t('syncPreview:section_updated')}</Heading>
                    <Tag colorScheme="orange">±{data.updated_subscriptions.length}</Tag>
                  </HStack>
                  <Stack spacing={2}>
                    {data.updated_subscriptions.map(renderUpdatedCard)}
                  </Stack>
                </Box>
              )}
            </Stack>
          )}
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: exit 0.

- [ ] **Step 3: Lint changed file**

```bash
cd frontend && npm run lint 2>&1 | grep -A2 SyncPreviewDrawer
```

Expected: no errors (warnings on `any` etc. would be fine, but the code uses `unknown`, no `any`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/mailboxes/SyncPreviewDrawer.tsx
git commit -m "feat(frontend): add SyncPreviewDrawer component"
```

---

## Task 9: "View" link on mailbox card

**Files:**
- Modify: `frontend/src/components/mailboxes/MailboxesPage.tsx`

- [ ] **Step 1: Add drawer state at the top of the component**

Find the existing component (around the other `useState` calls) and add:

```tsx
const [previewSyncId, setPreviewSyncId] = useState<string | null>(null)
```

Import `SyncPreviewDrawer` at the top of the file:

```tsx
import { SyncPreviewDrawer } from './SyncPreviewDrawer'
```

- [ ] **Step 2: Add a "View" link next to "+N new this run"**

Find the existing "New This Run" block. Replace it with:

```tsx
{mailbox.last_sync_new_emails_count !== null && (
  <HStack justify="space-between">
    <Text fontSize="sm" fontWeight="medium">
      New This Run:
    </Text>
    <HStack spacing={2}>
      <Text
        fontSize="sm"
        color={mailbox.last_sync_new_emails_count > 0 ? 'green.600' : 'text.subtle'}
      >
        {mailbox.last_sync_new_emails_count > 0
          ? `+${mailbox.last_sync_new_emails_count} new email${mailbox.last_sync_new_emails_count === 1 ? '' : 's'}`
          : 'No new emails'}
      </Text>
      {mailbox.last_sync_new_emails_count > 0 && mailbox.last_sync_history_id && (
        <Button
          size="xs"
          variant="link"
          colorScheme="blue"
          onClick={() => setPreviewSyncId(mailbox.last_sync_history_id)}
        >
          {t('syncPreview:view_link', { defaultValue: 'View' })}
        </Button>
      )}
    </HStack>
  </HStack>
)}
```

If `useTranslation` isn't already in the file, add `const { t } = useTranslation(['syncPreview'])` (and `import { useTranslation } from 'react-i18next'`). If the file already hard-codes English without `t()`, just hard-code `View` and skip the i18n on this single button — match the file's existing convention.

- [ ] **Step 3: Render the drawer at the bottom of the JSX (just before the page's closing tag)**

```tsx
<SyncPreviewDrawer
  syncHistoryId={previewSyncId}
  isOpen={!!previewSyncId}
  onClose={() => setPreviewSyncId(null)}
/>
```

- [ ] **Step 4: Typecheck and lint**

```bash
cd frontend && npx tsc --noEmit && npm run lint 2>&1 | grep -A2 MailboxesPage
```

Expected: typecheck exit 0, lint no new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/mailboxes/MailboxesPage.tsx
git commit -m "feat(frontend): add View link on mailbox card opening sync preview drawer"
```

---

## Task 10: Notification feed click handler dispatch

**Files:**
- Modify: `frontend/src/components/notifications/NotificationListPage.tsx`

- [ ] **Step 1: Add the icon and label cases**

In `getNotificationIcon` switch (around line 168), add:

```tsx
case 'sync_preview_available':
  return '🔍'
```

In `getNotificationTypeLabel` switch (around line 188), add:

```tsx
case 'sync_preview_available':
  return 'Sync preview'
```

- [ ] **Step 2: Add drawer state and dispatch**

At the top of the component (with the other `useState`):

```tsx
const [previewSyncId, setPreviewSyncId] = useState<string | null>(null)
```

Import the drawer:

```tsx
import { SyncPreviewDrawer } from '../mailboxes/SyncPreviewDrawer'
```

In the existing notification row's `onClick` handler (line 327), augment it so that for `sync_preview_available` notifications it also opens the drawer:

```tsx
onClick={() => {
  if (!notification.is_read) {
    handleMarkAsRead(notification.id)
  }
  if (notification.type === 'sync_preview_available') {
    const sid = (notification.notification_metadata as Record<string, unknown> | null)?.['sync_history_id']
    if (typeof sid === 'string') {
      setPreviewSyncId(sid)
    }
  }
}}
```

The cast tolerates a missing or differently-typed metadata field; only opens the drawer if the field is a string.

- [ ] **Step 3: Render the drawer at the bottom of the JSX**

Same pattern as Task 9:

```tsx
<SyncPreviewDrawer
  syncHistoryId={previewSyncId}
  isOpen={!!previewSyncId}
  onClose={() => setPreviewSyncId(null)}
/>
```

- [ ] **Step 4: Typecheck and lint**

```bash
cd frontend && npx tsc --noEmit && npm run lint 2>&1 | grep -A2 NotificationListPage
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/notifications/NotificationListPage.tsx
git commit -m "feat(frontend): open sync preview drawer from notification feed"
```

---

## Task 11: Manual smoke + linters + PR

- [ ] **Step 1: Run backend lint**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m black --check app/ alembic/versions/
docker-compose -f docker-compose.dev.yml exec -T backend python -m flake8 app/ alembic/versions/ --max-line-length=120
```

Expected: black clean, flake8 no NEW errors on changed files (pre-existing baseline acceptable).

- [ ] **Step 2: Run frontend lint**

```bash
cd frontend && npm run lint 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 3: Run backend tests**

```bash
docker-compose -f docker-compose.dev.yml exec -T backend python -m pytest tests/ -k "sync or notification or subscription or mailbox" --tb=short -q | tail -5
```

Expected: same baseline as before (`test_create_mailbox_connection_test_fails` is the only known failure).

- [ ] **Step 4: Trigger a real sync to verify end-to-end**

In a browser session:
1. Trigger a manual sync on a mailbox via the existing UI.
2. Wait for sync completion (watch backend logs).
3. Confirm a notification appears in the feed with type `sync_preview_available`.
4. Click the notification → drawer opens → renders New / Updated sections (or "Nothing new").
5. Reload Mailboxes page, hard refresh — confirm the "View" link appears next to "+N new" and opens the same drawer.
6. Click on a subscription card → routes to `/subscriptions/{id}`.

- [ ] **Step 5: Push branch and open PR**

```bash
git push -u origin feat/post-sync-subscription-preview
gh pr create --title "feat: post-sync subscription preview" --body "$(cat <<'EOF'
## Summary

Adds a right-side drawer that shows what the latest sync run actually produced — new subscriptions (auto-saved vs pending-review badges) and updated subscriptions (price changes, plus a hook for cancellation detection once that feature lands). Two entry points: an in-app `SYNC_PREVIEW_AVAILABLE` notification and a "View" link next to "+N new this run" on the mailbox card.

## Highlights

- Migration `o4o4o4o4o4o4`: `subscriptions.discovered_via_sync_history_id`, `price_history.sync_history_id`, `mailboxes.last_sync_history_id` (additive, nullable, indexed).
- Migration `p5p5p5p5p5p5`: `SYNC_PREVIEW_AVAILABLE` enum value via `ALTER TYPE … ADD VALUE IF NOT EXISTS`.
- New endpoint `GET /api/sync-history/{id}/preview` returning `{ sync_history, new_subscriptions, updated_subscriptions }`.
- Confidence-bucket derived server-side from `subscription.confidence_score` (≥ 85 = `auto_saved`, otherwise `pending_review`).
- Drawer reuses the styling pattern of the admin sync-errors detail drawer.

## Spec & plan

- Spec: `docs/superpowers/specs/2026-05-02-post-sync-subscription-preview-design.md`
- Plan: `docs/superpowers/plans/2026-05-02-post-sync-subscription-preview.md`

## Test plan

- [x] `pytest tests/test_sync_preview_api.py` — 4 tests pass.
- [x] `pytest -k "sync or notification or subscription or mailbox"` — same baseline (1 known fail).
- [x] `black --check`, `flake8` clean on changed files.
- [x] `npx tsc --noEmit` and `npm run lint` clean.
- [ ] Manual smoke: sync → notification → drawer renders → click-through routes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notes for the implementer

- **Subagent-driven execution recommended** for this plan — each task is independent and self-contained.
- **Branch**: already on `feat/post-sync-subscription-preview`. Don't switch.
- **Pre-commit hooks may run black on Python files**. If a task fails on commit because of formatting, just rerun `black app/` on the staged files and re-commit.
- **graphify-out/GRAPH_REPORT.md** churns on every commit (non-deterministic). Use `git restore graphify-out/GRAPH_REPORT.md` between tasks to keep the working tree clean.
- **i18n**: the existing `MailboxesPage.tsx` is mostly hardcoded English (no `useTranslation` hook). Match that convention — only the drawer itself uses `t()`. No need to migrate the whole page.
- **Cancellation detection**: the spec leaves room for surfacing `subscription.status` transitions (`active → pending_cancellation → cancelled`). Out of scope for v1; a future task can layer it on the existing `update_type='cancellation_detected'` path without API changes.
