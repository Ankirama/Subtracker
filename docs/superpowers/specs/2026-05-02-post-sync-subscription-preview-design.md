# Post-sync Subscription Preview — Design

**Status:** Draft (pending user review)
**Date:** 2026-05-02
**Owner:** ankirama

---

## 1. Context

The email sync pipeline now reports a per-run scoreboard on the mailbox card (`+N new this run`, `last run range`). The natural follow-up question is *what did those N new emails actually produce, and were any existing subscriptions modified?* Today the user has to scroll through `/subscriptions` and try to spot the new entries, which is unworkable as soon as the catalogue grows.

Mailbox syncs run automatically (daily/weekly schedule), so the user is not present at sync time. The preview must therefore be available *post-fact* — accessible through both passive (notification feed) and direct (mailbox card) entry points, and never as an auto-popup.

## 2. Goals

- After every sync that produced at least one new or updated subscription, the user can open a preview that lists exactly what changed.
- Two clearly separated buckets: **New** subscriptions created during the run, and **Updated** subscriptions where this run detected a change (price, cancellation).
- Inside *New*, distinguish auto-saved (≥ 85% confidence) from pending-review (50–84%) so the user knows where each one currently sits.
- Two entry points: a low-priority in-app notification when the sync completes (read passively) and a `View` link on the mailbox card next to `+N new this run` (recovers the same drawer if the notification was dismissed or buried).
- Click-through to the canonical subscription detail page if the user wants to act.
- No regression on existing sync flows.

## 3. Non-goals

- Inline edit / reject / "send to review" actions inside the preview. The preview is read-only — actions happen on the existing subscription detail page. Rationale: keeps scope small and avoids duplicating the existing edit surface (`SubscriptionModal.tsx`).
- Auto-popup on sync completion. Syncs run unattended; popups are friction, not value.
- Dedicated route / bookmarkable URL. A right-side `Drawer` (matching `AdminSyncErrorsPage`) is sufficient and consistent with the rest of the admin/user UI.
- Showing rejected emails (< 50% confidence). Those are not persisted as subscriptions, so they are out of scope here. Skipped emails are surfaced separately in the existing `SyncErrorsPage`.
- Backfilling preview for historical sync runs (the new `discovered_via_sync_history_id` column will be NULL for pre-existing rows).
- Mobile-specific layout work — the drawer's stock responsive behaviour is acceptable for v1.

## 4. Architecture

### 4.1 Backend data plumbing

A single new nullable FK on `subscriptions` is enough to identify the run that created a subscription:

```python
discovered_via_sync_history_id: Mapped[UUID | None] = Column(
    UUID(as_uuid=True),
    ForeignKey("sync_history.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```

Populated at INSERT inside `email_sync/stages/persistence.py` whenever the persistence stage creates a new `Subscription`. Manually-created subscriptions (`POST /api/subscriptions`) leave it NULL — that's the desired signal.

For the **Updated** bucket, the preview reads from the existing `price_history` table. Two implementation paths depending on what the table already exposes:

- **Path A (preferred):** add a nullable `sync_history_id` FK to `price_history`, populated at the same persistence step. Cheapest query.
- **Path B (fallback):** if adding the column is contentious or risks slowing the persistence stage, query by timestamp window (`price_history.created_at BETWEEN sync_history.started_at AND sync_history.completed_at`). Less precise but no migration impact.

Decision deferred to the implementation plan once the current schema of `price_history` is confirmed (see §7).

Cancellation detection: at the time of writing, the Cancellation Workflows feature is still in roadmap (Phase 1 unstarted). If no `cancellation_detected_*` columns exist on `subscriptions`, the *Updated* bucket only surfaces price changes for v1, and a TODO is left for cancellation surface once that feature lands.

Mailbox-side: a small mirror column `mailboxes.last_sync_history_id` (UUID FK, nullable) populated in the same finalisation block as the existing `last_sync_*` mirrors. This avoids a per-card extra query on the front (see §4.6) and lets the mailbox card open the latest preview without round-tripping through `sync_history`.

Migration `o4o4o4o4o4o4_add_sync_preview_links.py` (additive, nullable, indexed) covers all three columns:
- `subscriptions.discovered_via_sync_history_id`
- `price_history.sync_history_id` (only if Path A is taken — Path B leaves the table untouched)
- `mailboxes.last_sync_history_id`

Down-migration drops them.

### 4.2 API endpoint

```
GET /api/sync-history/{sync_history_id}/preview
```

Auth: requires the `sync_history.mailbox.user_id == current_user.id` (404 on mismatch).

Response shape:

```json
{
  "sync_history": {
    "id": "uuid",
    "mailbox_id": "uuid",
    "mailbox_email": "...",
    "started_at": "...",
    "completed_at": "...",
    "new_emails_count": 4
  },
  "new_subscriptions": [
    {
      "id": "uuid",
      "provider": "Netflix",
      "custom_label": null,
      "amount": 14.99,
      "currency": "EUR",
      "billing_cycle": "monthly",
      "category": "Entertainment",
      "confidence_bucket": "auto_saved",
      "source_email_subject": "Your Netflix bill",
      "source_email_date": "2026-05-01T08:14:00Z"
    }
  ],
  "updated_subscriptions": [
    {
      "id": "uuid",
      "provider": "Spotify",
      "update_type": "price_change",
      "before": { "amount": 9.99 },
      "after": { "amount": 11.99 },
      "source_email_subject": "Your subscription has been updated",
      "source_email_date": "2026-05-01T07:02:00Z"
    }
  ]
}
```

`confidence_bucket` is derived server-side from the existing confidence score: `auto_saved` if ≥ 85, `pending_review` otherwise. Subscriptions below 50% are not persisted and therefore never appear here.

`source_email_*` fields come from joining `subscription_emails` (existing junction table) → `email_messages`, picking the `extraction_role='initial_detection'` row for a New subscription, or the `'price_update'` row for an Updated one.

The endpoint returns even with empty arrays so the front-end can render a clean "Nothing new this run" empty state.

### 4.3 Notification trigger

A new enum value `SYNC_PREVIEW_AVAILABLE` is added to `notificationtype`, mirroring the migration pattern used for `SYNC_SKIPPED_MANY` / `SYNC_CIRCUIT_BREAKER`:

```python
op.execute(
    "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SYNC_PREVIEW_AVAILABLE'"
)
```

Trigger condition: in `app.tasks.email_sync.celery_tasks.run_email_sync_task`, after the sync completes successfully and the run-scoped metrics are computed, if `new_subscriptions ≥ 1 OR updated_subscriptions ≥ 1`, create one notification with priority `LOW` (informational, not actionable). Payload: `{ "sync_history_id": "...", "mailbox_id": "...", "new_count": ..., "updated_count": ... }`.

Implementation lives in `app/services/sync_notification_service.py` next to the existing `notify_sync_skipped_many` / `notify_sync_circuit_breaker`.

### 4.4 Frontend — Drawer component

New component `frontend/src/components/mailboxes/SyncPreviewDrawer.tsx`. Right-side Chakra `Drawer` (`size="lg"`), consistent with `AdminSyncErrorsPage` detail drawer.

Contents:

- **Header:** `Sync preview — <mailbox email>`, with sub-line `Completed <relative date>, +N new emails`.
- **Section "New" (badge `+N`):** vertically-stacked cards. Each card shows
  - provider + optional `custom_label`,
  - amount + currency + billing cycle,
  - category badge,
  - confidence badge: green `Auto-saved` or orange `Pending review`,
  - one-line preview of the source email subject + date.
  - Whole card is clickable → routes to `/subscriptions/{id}`.
- **Section "Updated" (badge `±N`):** same card layout, with a single highlight line per change type:
  - `price_change`: `13.99€ → 17.99€` with arrow and red/green colouring depending on direction.
  - `cancellation_detected`: `Cancellation detected`.
- **Empty state:** if both arrays are empty, render `Nothing new this run.` (and the drawer should normally not be triggered in this case, but defensive).
- **Loading state:** Chakra `Spinner` while the React Query call is pending.

State management: a single React Query hook `useSyncPreview(syncHistoryId)` keyed on `['sync-preview', syncHistoryId]` with default `staleTime: 60_000`.

### 4.5 Frontend — Trigger #1: notification feed

Existing notification feed (`NotificationListPage` or wherever notifications render) already routes notifications to a click handler keyed by type. Add a branch for `SYNC_PREVIEW_AVAILABLE` that opens the drawer with the `sync_history_id` from the notification payload. Clicking the notification marks it read (existing behaviour).

### 4.6 Frontend — Trigger #2: mailbox card "View" link

On `MailboxesPage.tsx`, next to the existing `New This Run: +N new emails` line, append a small `View` link / button when `mailbox.last_sync_new_emails_count > 0` *or* the most recent sync produced any updated subscriptions. The link opens the drawer with the latest sync_history_id of that mailbox.

To know the latest sync_history_id without an extra query per card, mirror it on the mailbox row — add `mailbox.last_sync_history_id` (UUID FK, nullable, set in the same finalisation block). Tiny additional column, big simplification on the front.

### 4.7 i18n

New namespace `syncPreview` (en + fr), registered alongside `syncErrors` and `adminSyncErrors`. Approximately 10–12 keys: section titles, badges, empty state, action labels.

## 5. Test plan

Backend:
- Unit test on the API endpoint: returns 404 on someone else's sync_history; returns the right shape on success; bucketing logic for confidence boundaries.
- Integration test on the persistence stage: a new subscription gets `discovered_via_sync_history_id` populated; a price update gets the right linkage.
- Notification creation logic: notification only fires when at least one new/updated sub exists.

Frontend:
- Drawer renders correctly for the three states (loading / data / empty).
- Click on a card routes to subscription detail.
- Notification click opens drawer with right `sync_history_id`.
- "View" link on mailbox card disabled when no new/updated subs.

Manual smoke:
- Trigger a real Gmail sync that pulls new subscriptions → confirm notification appears, drawer opens, all sections render.
- Trigger an incremental sync that finds nothing → no notification.
- Trigger a sync that detects a price change on an existing sub → "Updated" section renders.

## 6. Effort estimate

~1 day, split:

- Backend: migration + persistence wiring + endpoint + notification trigger + tests — 3-4h.
- Frontend: drawer component + hook + 2 triggers + i18n + types — 3-4h.
- Final integration / manual smoke / PR — 1h.

## 7. Open questions / risks

These will be resolved during the implementation plan, not before:

1. **`price_history` schema:** does it already have `sync_history_id`, a usable `created_at`, or neither? Determines Path A vs Path B in §4.1.
2. **Pending-review surface:** is "pending review" represented by a dedicated `status` column, by `confidence_score` alone, or by membership in a separate review table? Affects whether the badge is computed from a stored field or a derived one.
3. **Cancellation detection:** until the Cancellation Workflows feature lands (Phase 1 still unstarted in the roadmap), the *Updated* bucket may only ever contain `price_change`. Acceptable for v1; document the gap.
4. **Notification feed click handler:** verify the existing dispatcher recognises notification types via a switch, and that adding a new branch is non-invasive.

## 8. Rollout

- Migration is purely additive; no production data risk.
- New notification type added via `ALTER TYPE ADD VALUE IF NOT EXISTS` — re-runnable.
- New columns on `subscriptions` and `mailboxes` are nullable; pre-existing rows naturally have NULL until a fresh sync populates them.
- Frontend gates the `View` link on `last_sync_new_emails_count > 0` so it stays hidden for mailboxes that have not synced under the new code yet.
