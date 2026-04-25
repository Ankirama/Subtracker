# Backend Architecture Audit — 2026-04-25

> Targeted audit of the 5 largest backend Python modules (~5,665 LoC total).
> Driven by the C decomposition (sub-project C6).
>
> **Spec:** `docs/superpowers/specs/2026-04-25-c6-backend-architecture-audit-design.md`
> **Plan:** `docs/superpowers/plans/2026-04-25-c6-backend-architecture-audit.md`

## Method

This audit applies a fixed per-file template (Symptômes / Responsabilités identifiées / Couplages / Couverture tests / Proposition de découpe / Effort & dépendances) to the 5 largest backend Python files, then synthesises three cross-cutting sections:

- **§A — Constats transverses** — duplication patterns, layer violations, circular imports affecting 2+ files.
- **§B — Roadmap priorisée** — recommended execution order with justification.
- **§C — Out-of-scope** — items noted but not addressed in this audit.

Source data: the source files themselves, their associated test files (if any), and `graphify-out/GRAPH_REPORT.md`. T-shirt sizing (S/M/L/XL), not hour estimates.

## §1 — `backend/app/api/subscriptions.py` — 1441 lines

### Symptômes

Single FastAPI router file aggregating **17 endpoints** (one inline helper plus 17 `@router.*` decorators between lines 61 and 1256) covering CRUD, stats, analytics, duplicate detection, merge/split, status reconciliation, feedback capture, price history, and AI cancellation-suggestion workflows. The file mixes thin CRUD handlers (e.g. `delete_subscription`, lines 736-763) with heavy in-handler business logic — `get_analytics_trends` alone spans **162 lines** (272-433) and reimplements monthly cost projection from scratch with nested loops, `defaultdict`, and `relativedelta` arithmetic. Two **lazy intra-function imports** betray the layering issue: line 783 imports from `app.tasks.email_sync` and line 1045 imports from `app.services.renewal_calculator`, indicating the module reaches into both the Celery layer and an additional service to avoid module-level circulars. Section structure is implicit: there are no `# === chapter ===` markers, only a lone `# Price History Endpoints` divider at line 964, so concerns are interleaved by historical accretion rather than by design. Cost-projection logic (`amount * 12`, `amount / 12`, `amount * 4.33`, `amount / 3`, `amount / 6`) is **duplicated three times** — at 207-217, 229-236, and 327-338 — confirming the absence of a shared helper. The file imports six SQLAlchemy models directly (User, Mailbox, Subscription, subscription_emails, SubscriptionFeedback, PriceHistory) and mutates the `subscription_emails` association table by raw SQL in two distinct endpoints (merge at 595-599, split at 1406-1411), so the API layer also acts as a partial repository.

### Responsabilités identifiées

1. **CRUD subscription** (lines 61-107, 632-733, 736-763) — `create_subscription`, `get_subscription`, `update_subscription`, `delete_subscription`. Standard resource lifecycle.
2. **List & filter** (lines 109-169) — `list_subscriptions` with mailbox/status/category/trial filtering and pagination.
3. **Stats agrégées** (lines 172-268) — `get_subscription_stats`: monthly/yearly cost rollup, by-category, by-cycle, upcoming renewals.
4. **Analytics historiques** (lines 271-433) — `get_analytics_trends`: 162-line monthly time-series engine with inline cost projection, category trends, peak detection.
5. **Détection / résolution de doublons** (lines 436-507, 510-629) — `find_duplicate_subscriptions` (heuristic grouping + similarity scoring) and `merge_subscriptions` (transactional merge with price-history side-effects and raw `subscription_emails` SQL).
6. **Réconciliation de statut** (lines 766-839, 1030-1134) — `update_subscription_status` (delegates to `app.tasks.email_sync.update_subscription_statuses` via lazy import) and `update_subscription_renewal_status` (re-runs `RenewalCalculator` over all user subs from inside the request handler — 100+ lines of orchestration).
7. **Feedback collection (ML training data)** (lines 842-961) — `create_subscription_feedback`: builds a JSON snapshot of the subscription before deletion for AI feedback loops.
8. **Price history (passe-plat)** (lines 967-1027) — `get_subscription_price_history`, `get_subscription_price_statistics`: thin wrappers over `PriceHistoryService`.
9. **Cancellation suggestion workflow** (lines 1137-1253) — `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion`: AI suggestion lifecycle (apply / clear).
10. **Manual split** (lines 1256-1441) — `split_subscription`: 185-line endpoint that re-creates subscriptions and rewires the `subscription_emails` association table by raw SQL.

### Couplages (graph-derived)

- **Imports entrants**: 1 module imports the router — `backend/app/main.py:133` only (re-exports as `/api/subscriptions`). No service or task imports symbols from this file, which is healthy: the router is a leaf in the import DAG.
- **Imports sortants**: 14 modules. Notable / surprising:
  - `app.models.email_message.subscription_emails` (association table) — used to perform raw `db.execute(subscription_emails.update()...)` mutations directly from the API layer (merge line 595, split line 1406). This bypasses both `Subscription` and any repository abstraction.
  - **Cross-layer lazy imports** (in-function): `from app.tasks.email_sync import update_subscription_statuses` (line 783) and `from app.services.renewal_calculator import RenewalCalculator, get_subscription_emails` (line 1045). Their placement inside handlers is a deliberate workaround — likely for circular-import avoidance — and signals that these endpoints conceptually belong to those layers, not to the API.
  - 6 model imports + 2 schema modules + 1 service (`PriceHistoryService`) + auth deps. No frontend / no infra.
- **Centrality**: `api/subscriptions.py` itself is **not named** as a god node in `GRAPH_REPORT.md`, but its central domain entity `Subscription` is flagged at **0.145 betweenness centrality** (line 1266) bridging Communities 0/1/2/3/4/6/8/9/11/12/13/15/16/17, and `Subscription` carries **816 inferred edges** (line 1272). The file is the principal HTTP surface for that high-centrality entity, which explains its size.

### Couverture tests

- Test file: `backend/tests/test_subscriptions_api.py` (899 lines, **40 `def test_` functions**).
- Approximate coverage estimate: **~65% of routes** have at least one happy-path + auth test. Tests cover: list (5 cases), get-by-id (3), create (3), update (3), delete (3), stats (3), update-status (2), analytics-trends (5), feedback (4), price-history (4), price-statistics (4). **Routes with zero tests**: `find_duplicate_subscriptions`, `merge_subscriptions`, `update_subscription_renewal_status`, `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion`, `split_subscription`. Notably the six untested routes are the **most complex and most mutation-heavy** in the file (transactional merges, raw association-table SQL, multi-subscription rewrites).
- Refactor safety: **risky**.
- Justification: the simple CRUD/list/stats/analytics surface (≈ 60% of LoC) is well-tested and can be extracted safely; but the ~480 lines of merge / split / renewal-reconciliation / cancellation-suggestion logic has **no test scaffold**, and the merge and split paths perform raw SQL mutations on `subscription_emails` that would be silently broken by an extraction error. Any decomposition of those endpoints **must be preceded by characterisation tests**.

### Proposition de découpe

```
backend/app/api/subscriptions/
├── __init__.py          (~10 lines — package marker)
├── router.py            (~60 lines — APIRouter assembly + verify_mailbox_ownership helper)
├── crud.py              (~280 lines — POST /, GET /, GET /{id}, PUT /{id}, DELETE /{id})
├── stats.py             (~100 lines — GET /stats)
├── analytics.py         (~165 lines — GET /analytics/trends)
├── duplicates.py        (~75 lines — GET /duplicates)
├── merge_split.py       (~310 lines — POST /{id}/merge/{target_id}, POST /{id}/split)
├── status_reconcile.py  (~180 lines — POST /update-status, POST /update-renewal-status)
├── feedback.py          (~125 lines — POST /feedback)
├── price_history.py     (~65 lines — GET /{id}/price-history, GET /{id}/price-statistics)
└── cancellation_suggestion.py (~120 lines — POST /{id}/accept-suggestion, POST /{id}/dismiss-suggestion)
```

Total ≈ 1490 lines (slight overhead from per-file imports and `__init__.py`). The split aligns with the 10 responsibilities identified above and uses **stable axes** unlikely to drift: HTTP verbs cluster naturally per resource, and the cross-cutting verbs (merge/split, status reconcile, cancellation suggestion) get their own files because they have **distinct invariants** (transactional, raw-SQL, AI-driven) that justify isolation. Pulling cost-projection arithmetic out of `stats.py` and `analytics.py` into a shared `app/services/cost_projection.py` (≈ 40 lines) eliminates the triplicate `monthly/yearly/weekly/quarterly/biannual` arithmetic. The two lazy intra-function imports collapse to module-level imports inside `status_reconcile.py`, which has no reason to be imported by the lazy-loaded modules.

### Effort & dépendances

- **Effort**: **M**.
- **Justification effort**: ~60% of LoC is mechanical move-and-import; ~40% (merge, split, renewal reconciliation, cancellation-suggestion) requires writing characterisation tests **before** moving, plus extracting the cost-projection helper. Estimated 4-6h: 1h scaffold the sub-package, 2h move tested endpoints + run `test_subscriptions_api.py`, 2h write characterisation tests for the 6 untested routes, 1h move them. No public API URL changes (router prefix `/api/subscriptions` stays in `main.py`).
- **Bloqueurs**: _None._ The file is a leaf in the import DAG; only `main.py` imports it. No upstream refactor required.
- **Bloquant pour**: §A cross-cutting work on cost-projection duplication (the same arithmetic appears in `tasks/email_sync.py` and likely in `services/`). Splitting this file first lets §A target a single shared helper rather than chasing inline copies.
- **Risque**: **medium**.
- **Justification risque**: HTTP contracts are stable (only `main.py` consumes the router; frontend uses the URL paths, not Python imports), but the merge and split paths mutate the `subscription_emails` association table via raw SQL with **zero test coverage** — an accidental import-path or transaction-scope change would corrupt data silently. Mitigation: write `test_merge_subscriptions.py` and `test_split_subscription.py` characterisation tests **before** moving those handlers; treat them as a quality gate.

## §2 — `backend/app/tasks/email_sync.py` — 1410 lines

### Symptômes

A single Celery task module that bundles **2 task entry points** (`sync_mailbox_emails` line 938, `check_scheduled_syncs` line 1320) plus **3 module-level helpers** (`filter_subscription_data` line 63, `update_subscription_statuses` line 1198, `parse_date_filter` line 1282), but the bulk of the file is a single **820-line god function**: `_sync_mailbox_async` runs from line 88 to line 922 and orchestrates every stage of the pipeline inline — credential decryption, provider instantiation, date-filter resolution, paginated fetch, classification, extraction, deduplication / service-reference matching, subscription upsert, price-history bookkeeping, renewal calculation, cancellation-suggestion creation, association-table writes, progress persistence, cancellation polling, and history-entry updates. Three **lazy intra-function imports** (line 156 `app.services.ai_classifier`, line 157 `app.services.subscription_extractor`, line 487 `app.services.reference_extractor`) confirm circular-import pressure between this task module and the AI services layer. A nested `try/except` block 5 levels deep (lines 334-808) wraps the per-email processing, and the duplicate-resolution heuristic (service references → email_sender match → custom_label keywords → fallback to first match, lines 462-576) is **115 lines of inline policy** with magic-keyword lists (`"tier"`, `"channel"`, `"plan"`, …) and a hard-coded payment-processor list (`"paypal"`, `"stripe"`, `"paddle"`, `"gumroad"`, `"fastspring"`, line 451) embedded in the orchestrator. Price-change arithmetic (`(new - old) / old * 100`, classified into `"increase"`/`"decrease"`) is **duplicated twice** at lines 374-394 (AI-flagged price update) and 602-625 (post-hoc detection on update). The orchestrator persists progress (`mailbox.last_sync_*`, `current_batch_number`, `progress_percentage`, `estimated_completion_time`, history-entry fields) inline at three different commit points in the same loop body, and the `sync_mailbox_emails` Celery task itself reimplements **80+ lines of completion / failure / auth-error bookkeeping** (lines 1045-1195) that mirrors the in-loop bookkeeping.

### Responsabilités identifiées

1. **Task entry point — interactive sync** (lines 925-1195) — `sync_mailbox_emails`: Celery task with retry policy, resume-from-interrupted detection, history-entry creation, completion/failure/auth-error finalisation.
2. **Task entry point — scheduled sync** (lines 1315-1410) — `check_scheduled_syncs`: periodic Celery beat task that scans mailboxes with `daily`/`weekly` `sync_frequency` and dispatches `sync_mailbox_emails.delay()`.
3. **Async orchestrator** (lines 88-922) — `_sync_mailbox_async`: 820-line god function holding the entire pipeline; imports AI services lazily to break circulars.
4. **Provider bootstrap** (lines 112-130) — credential decryption, JMAP/Gmail factory dispatch (duplicates the factory-pattern intent of `app.email_providers`), authenticate with auth-error re-raise.
5. **Date-filter resolution** (lines 132-153, 1282-1312) — explicit filter > last_sync > mailbox default > admin config; `parse_date_filter` parses `Ndays`/`Nmonths`/`Nyears` strings.
6. **Stage 1 — Classification** (lines 207-275) — fetch batch, dedup by `Message-ID`, filter system emails via `should_process_email`, batch-classify via `classify_emails_batch`, persist `EmailMessage` rows.
7. **Stage 2 — Extraction selection** (lines 277-328) — decide which emails need extraction (new subscription emails always; existing ones only if not already linked), call `extract_subscriptions_batch`.
8. **Stage 3 — Subscription upsert with multi-strategy dedup** (lines 330-803) — service-reference matching, payment-processor handling, email_sender / custom_label / first-match fallback, price-update detection, subscription create/update with `filter_subscription_data`, association-table insert, renewal calculation via `RenewalCalculator`, cancellation-suggestion creation.
9. **Price-history bookkeeping** (lines 372-398, 600-625, 647-661) — three separate code paths (AI-flagged update, post-hoc change detection, initial creation) that all instantiate `PriceHistory` rows with similar percentage / change-type arithmetic.
10. **Progress & history persistence** (lines 810-906) — per-batch update of `mailbox.last_sync_*` resume fields, `current_batch_number`, `total_batches_estimate`, `progress_percentage`, `estimated_completion_time`; cancellation polling via `db.refresh(mailbox)`; cancellation finalisation of `SyncHistory` entry.
11. **Subscription activity reconciliation** (lines 1198-1279) — `update_subscription_statuses`: scans all subs for a mailbox, applies grace-period table (weekly/monthly/quarterly/biannual/yearly), flips `is_active` based on `last_confirmed_at`. Also exported and consumed by `app.api.subscriptions` (line 783).
12. **`DatabaseTask` base class** (lines 68-85) — Celery `Task` subclass that lazily creates and closes a SQLAlchemy session per task invocation.

### Couplages (graph-derived)

- **Imports entrants**: 3 modules import from this file.
  - `backend/app/api/mailboxes.py:355, :474` — both lazy intra-function imports of `sync_mailbox_emails` (suggesting `mailboxes.py` is also fighting circulars; same anti-pattern as `api/subscriptions.py`).
  - `backend/app/api/subscriptions.py:783` — lazy intra-function import of `update_subscription_statuses` (already documented in §1).
  - `backend/tests/test_email_sync.py:11` — module-level import for tests.
  - The fact that **every production caller uses lazy imports** is itself the diagnostic finding: this module is a circular-import hub for the API layer.
- **Imports sortants**: this file imports from **17 distinct modules**, of which 3 are intra-function (lazy):
  - Module-level (14): `celery`, `sqlalchemy.orm`, `app.celery_app`, `app.database`, 5 model modules (`mailbox`, `subscription`, `email_message`, `price_history`, `sync_history`), 2 provider modules (`app.email_providers`, `app.email_providers.gmail`), `app.security.encryption`, `app.config`, `app.utils.config_helper`, `app.services.renewal_calculator`, `app.services.email_filter`.
  - **Lazy / cross-layer** (3): `app.services.ai_classifier` (line 156), `app.services.subscription_extractor` (line 157), `app.services.reference_extractor` (line 487). These three services almost certainly consume something this module also exports (likely shared types or DB models), making the circular hard to break without an interface seam.
- **Centrality**: `email_sync.py` itself is **not named** as a god node in `GRAPH_REPORT.md`, but it appears in the "Surprising Connections" section at line 228-229: `_sync_mailbox_async()` is flagged with an inferred call to `isInstance()` in a frontend workbox bundle — a graph-extraction artefact, but the listing confirms `_sync_mailbox_async` is a high-fan-out node. The downstream entities `Subscription`, `Mailbox`, `EmailMessage`, `PriceHistory` are all in the GRAPH_REPORT top-10 inferred-edge list (816 / 305 / 136 / 148 edges respectively, lines 217-225 of GRAPH_REPORT) and **all four are written by this single function**.

### Couverture tests

- Test file: `backend/tests/test_email_sync.py` (518 lines, **22 `def test_` functions**, 3 test classes: `TestParseDateFilter` 9 tests, `TestUpdateSubscriptionStatuses` 5 tests, `TestSyncMailboxEmails` 8 tests).
- Approximate coverage estimate: **~30-40% of LoC**. The two small helpers are well-covered: `parse_date_filter` has 9 happy-path + edge-case tests (singular/plural, whitespace, case, default fallback), and `update_subscription_statuses` has 5 tests (activation, deactivation, manual-override, weekly cycle, yearly cycle). The Celery task itself has 8 tests but they are **outer-shell tests**: nonexistent mailbox, inactive mailbox, exception path, resume from cancelled, force-full-sync, custom date filter, progress-tracking clearance, and one "successful sync" test. Inspection of those tests (lines 267-518) shows they mock `_sync_mailbox_async` or its dependencies — the **inner pipeline (classification → extraction → dedup heuristic → price-history → renewal → cancellation suggestion → association-table writes) has zero behavioural coverage**. Specifically untested: service-reference matching (lines 485-509), payment-processor branch (lines 451-460, 527-533), email_sender / custom_label disambiguation (lines 535-576), AI-flagged price-update path (lines 345-440), post-hoc price-change detection (lines 580-630), renewal-calculator integration (lines 664-731), cancellation-suggestion creation (lines 733-767), and the cancellation-polling + history-entry update on cancel (lines 863-899).
- Refactor safety: **risky**.
- Justification: outer Celery-task contract (input UUID, retry policy, status fields, return shape) is well-tested and would survive an extraction unchanged; but ~600 of the 820 lines inside `_sync_mailbox_async` represent **untested business policy** (multi-strategy dedup, three price-history paths, cancellation suggestion, renewal recalculation, progress persistence). Any extraction that re-orders, re-commits, or re-rolls-back differently could silently change which emails get classified, which subscriptions get merged versus duplicated, or whether progress survives interruption — and there is no characterisation harness to catch it.

### Proposition de découpe

```
backend/app/tasks/email_sync/
├── __init__.py             (~15 lines — re-exports sync_mailbox_emails, check_scheduled_syncs,
│                                       update_subscription_statuses, parse_date_filter for back-compat)
├── celery_tasks.py         (~280 lines — DatabaseTask, sync_mailbox_emails entry point with
│                                       retry policy + resume detection + history finalisation,
│                                       check_scheduled_syncs scheduler)
├── orchestrator.py         (~180 lines — _sync_mailbox_async: provider bootstrap, date-filter
│                                       resolution, top-level batch loop, progress persistence,
│                                       cancellation polling)
├── stages/
│   ├── __init__.py         (~5 lines)
│   ├── classification.py   (~100 lines — fetch + Message-ID dedup + system-email filter +
│                                       classify_emails_batch + EmailMessage row creation)
│   ├── extraction.py       (~80 lines — extraction-needs decision + extract_subscriptions_batch)
│   └── persistence.py      (~250 lines — multi-strategy dedup, subscription upsert,
│                                       association-table writes, calls into price_history.py
│                                       and renewal_step.py and cancellation_step.py)
├── dedup_strategy.py       (~140 lines — service-reference matching, payment-processor list,
│                                       email_sender / custom_label / first-match fallback;
│                                       extracted from lines 441-576)
├── price_history.py        (~90 lines — record_price_update(), record_initial_price(),
│                                       record_price_change() — collapses 3 inline paths
│                                       at lines 372-398, 600-625, 647-661 into one helper)
├── renewal_step.py         (~70 lines — wraps RenewalCalculator + reactivation detection
│                                       from lines 664-731)
├── cancellation_step.py    (~50 lines — cancellation suggestion creation from lines 733-767)
├── progress_tracker.py     (~80 lines — mailbox progress fields + history-entry mutations,
│                                       extracted from lines 810-906 and 1045-1195)
├── filters.py              (~30 lines — VALID_SUBSCRIPTION_FIELDS, filter_subscription_data,
│                                       parse_date_filter)
└── status_reconciler.py    (~90 lines — update_subscription_statuses + GRACE_PERIODS table)
```

Total ≈ 1430 lines (slight overhead from per-file imports and `__init__.py`). The split exposes the **3-stage pipeline structure** that the file already advertises in comments (`# STAGE 1`, `# STAGE 2`, `# STAGE 3` at lines 207, 277, 330) but never reified into modules. **Three high-value seams** emerge: (a) `dedup_strategy.py` isolates the only truly hot-spot policy (the multi-strategy dedup with magic keyword lists), making it independently testable and replaceable when service-reference matching matures; (b) `price_history.py` collapses three duplicated arithmetic blocks into one helper that can also be reused by `api/subscriptions.py` (which performs similar logic in merge); (c) `progress_tracker.py` removes the persistence chatter from the orchestrator so the loop body reads as a pipeline, not as a state machine. The 3 lazy intra-function imports collapse to clean module-level imports inside `stages/classification.py`, `stages/extraction.py`, and `dedup_strategy.py` because none of those sub-modules need to import back from `celery_tasks.py`. Module-level re-exports in `__init__.py` preserve the existing public surface (`from app.tasks.email_sync import sync_mailbox_emails, update_subscription_statuses, parse_date_filter`) so the 3 inbound import sites in `api/mailboxes.py` and `api/subscriptions.py` and `tests/test_email_sync.py` work unchanged.

### Effort & dépendances

- **Effort**: **L**.
- **Justification effort**: ~30% of LoC has tests and is a mechanical move (the two helpers, the Celery task shell, `parse_date_filter`); ~70% — the 600 untested lines of `_sync_mailbox_async` business logic — requires writing **characterisation tests before extracting**, especially for the multi-strategy dedup, the three price-history paths, and the cancellation suggestion flow. Roughly: 2h scaffold the sub-package and move the tested helpers (`parse_date_filter`, `update_subscription_statuses`, `DatabaseTask`, `filter_subscription_data`); 4h write characterisation tests for dedup strategy, price-history paths, renewal step, cancellation step (using factory/fixture builders for `EmailMessage`+`Subscription` graphs); 4h extract `dedup_strategy.py` + `price_history.py` + `renewal_step.py` + `cancellation_step.py` and rewire the orchestrator; 2h extract `progress_tracker.py` and the stage modules; 2h-4h iterate on the inevitable hidden coupling (commit boundaries, lazy-vs-eager flush, association-table relationship checks). Realistic 12-16h.
- **Bloqueurs**: _None._ The 3 inbound callers (`api/mailboxes.py`, `api/subscriptions.py`, `test_email_sync.py`) all import named symbols that can be re-exported from `__init__.py` for compatibility.
- **Bloquant pour**: §A cross-cutting work on (a) cost-projection / price-change arithmetic duplication shared with `api/subscriptions.py`, (b) circular-import hygiene between the API layer and AI services (`api/subscriptions.py` lazy import of `email_sync`, `email_sync` lazy imports of three AI services). Splitting this file lets §A target a single shared helper module (`app/services/price_history_recorder.py`) instead of chasing inline copies, and the new `dedup_strategy.py` becomes the canonical home for dedup policy that `api/subscriptions.find_duplicate_subscriptions` (currently 71 lines of inline scoring at §1 lines 436-507) could also delegate to.
- **Risque**: **high**.
- **Justification risque**: this code is **on the data-write path for every subscription, every email, every price-history entry, and every association-table row** — the four highest-edge entities in the graph (`Subscription` 816, `Mailbox` 305, `PriceHistory` 148, `EmailMessage` 136). The 5-level-deep `try/except` + per-email `db.commit()` + `db.rollback()` (line 803, 807) means transaction granularity is implicit and **any extraction that accidentally hoists a commit out of the per-email scope will batch-corrupt rollback semantics**. The cancellation polling reads `mailbox.sync_cancellation_requested` after `db.refresh(mailbox)` (line 864) — moving that out of the orchestrator without preserving the refresh-then-read ordering will silently break user-initiated cancellations. Mitigation: **mandatory characterisation tests before any extraction**; use a transaction-checkpoint test fixture that records `db.commit()` / `db.rollback()` call counts and verifies they are unchanged after refactor; treat the 600 untested lines as a quality gate identical to the merge/split paths flagged in §1.



## §3 — `backend/app/api/auth.py` — 1191 lines

_Pending audit._

## §4 — `backend/app/services/email_templates.py` — 841 lines

_Pending audit._

## §5 — `backend/app/services/email_service.py` — 782 lines

_Pending audit._

## §A — Constats transverses

_Pending cross-cutting analysis._

## §B — Roadmap priorisée

_Pending prioritisation._

## §C — Out-of-scope

_Pending listing._
