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

### Symptômes

Single FastAPI router file aggregating **19 endpoints** spanning seven distinct auth flows (registration with invite-token gating, login with brute-force tracking, refresh, logout, account management, two-factor authentication, and email verification) with only two implicit `# section` comments (`# Account Management Endpoints` line 484, `# Two-Factor Authentication Endpoints` line 695, `# Email Verification Endpoints` line 1031) marking the boundaries. The handlers carry heavy in-line policy: `register` (lines 64-203, **140 lines**) interleaves invite-token validation, duplicate-email detection, password hashing, user-row creation, invite-token consumption, frontend-URL composition, and email dispatch — the lone composite of business and side-effect logic for a single HTTP path. `login` (lines 206-355, **150 lines**) hard-codes the brute-force threshold (`failed_attempts >= 5` line 231), branches on 2FA method (`email`/`totp`), sends OTP emails inline, and creates JWTs — all in one function. **Two lazy intra-function imports** confirm circular-import pressure: `from app.models.invite_token import InviteToken` at line 86 (inside `register`) and `from app.security.password import verify_password` at line 672 (inside `delete_account`, redundant with the module-level import at line 35). The 2FA flow alone aggregates **6 endpoints** (`verify-login`, `setup`, `enable`, `disable`, `status`, `backup-codes/regenerate`) totalling ~330 lines (698-1028) that all share the same `if user.two_factor_enabled` / `else` branching pattern but never reify it into a guard. The "send verification email and bail with 500 if it fails" pattern is **duplicated three times** (lines 191-198 register, lines 316-321 login OTP send, lines 829-836 2FA email setup, lines 1180-1185 resend-verification), each rebuilding the `EmailService(db)` instance and the `(success, error)` tuple-handling. The `frontend_url + verification_url` construction is **duplicated twice** (lines 179-180 register, lines 1170-1171 resend-verification), and the `display_name = user_data.display_name or user_data.email.split("@")[0]` fallback appears in three forms (lines 184, 312, 825, 1175). Finally, the docstring for `register` still claims "If verification fails" (line 84) while the code actually returns 500 with a "try resending" message — minor doc/code drift inside the file itself.

### Responsabilités identifiées

1. **Registration & invite-token consumption** (lines 64-203) — `register`: invite-token validation (REQUIRE_INVITE_TOKEN gate, expiry/used/email-match checks), duplicate-email handling (with separate path for unverified accounts), password hashing, user-row creation, invite consumption, verification email dispatch.
2. **Login & brute-force protection & 2FA challenge dispatch** (lines 206-355) — `login`: in-memory failed-attempt tracking (5-strikes-in-15-min via `track_failed_login`), security-event logging across 4 distinct failure paths (invalid creds, unverified email, inactive account, brute-force), 2FA branching with inline email-OTP dispatch for `method=email`.
3. **Refresh token rotation** (lines 358-447) — `refresh_access_token`: JWT type-check (must be `refresh`), payload validation, user-existence + active-state recheck, security-event logging on each invalid-token path (4 distinct error reasons).
4. **Current-user info & logout** (lines 450-481) — `get_current_user_info`, `logout`: thin pass-throughs over `get_current_user` dependency; logout is documented as client-side stateless.
5. **Account profile management** (lines 487-524) — `update_profile`: display_name + email update (email change resets `email_verified=False`).
6. **Password change** (lines 527-559) — `change_password`: verifies current password, re-hashes new password.
7. **User preferences** (lines 562-652) — `update_preferences` (theme/language/currency/date_format/timezone via JSONB `settings`), `get_language_preference`, `update_language_preference` (separate first-class column `preferred_language`). Two parallel preference systems coexist for "language" — JSONB and dedicated column — without a clear contract for which wins.
8. **Account deletion** (lines 655-692) — `delete_account`: password verification + explicit `confirm` flag, then `db.delete(user)` (hard delete, no soft-delete or anonymisation).
9. **2FA login completion** (lines 698-775) — `verify_2fa_login`: stateless 2FA verification (re-fetches user by email each time, no challenge-token), backup-code path, security-event logging, JWT issue.
10. **2FA setup / enable / disable** (lines 778-969) — `setup_2fa` (TOTP returns `secret + qr_code`, email sends OTP), `enable_2fa` (verifies code, generates backup codes), `disable_2fa` (password-confirmed).
11. **2FA status & backup-code regeneration** (lines 972-1028) — `get_2fa_status` (returns enabled/method/backup_codes_remaining), `regenerate_backup_codes` (replaces existing codes).
12. **Email verification** (lines 1034-1107) — `verify_email`: IP-block check, brute-force tracking via `VerificationRateLimiter`, token verification, mark verified, **auto-login** (issues access + refresh tokens on success).
13. **Verification resend** (lines 1110-1191) — `resend_verification`: IP-block check, per-email rate limit (12/hour), enumeration-safe response (vague message even when email doesn't exist), email dispatch.

### Couplages (graph-derived)

- **Imports entrants**: 1 module imports the router — `backend/app/main.py:131` only (`auth.router` mounted at `/api/auth` via line 158). No service or task imports symbols from this file. Healthy import-DAG leaf, mirroring §1.
- **Imports sortants**: 16 module-level imports + 2 lazy intra-function imports.
  - Module-level (16): `fastapi`, `sqlalchemy.orm`, `jose`, `app.database`, `app.models.user`, `app.schemas.auth` (22 schema names), `app.security.password`, `app.security.jwt`, `app.security.dependencies`, `app.security.events` (3 names), `app.security.two_factor` (4 names), `app.services.email_service`, `app.security.email_verification` (2 names), `app.config`, `app.utils.config_helper`, `datetime`, `logging`. The fan-out into `app.security.*` (5 distinct sub-modules) is itself a smell: this router is the **only** consumer of most of those packages, and the abstraction boundary leaks (e.g. `TOTPManager`, `EmailOTPManager`, `BackupCodesManager` all imported at the API layer rather than hidden behind `TwoFactorAuth`).
  - **Lazy / cross-layer (2)**: `from app.models.invite_token import InviteToken` line 86 (inside `register`, almost certainly because import-time would create a circular through `User.invites` relationship), `from app.security.password import verify_password` line 672 (inside `delete_account`, **redundant** with the module-level import at line 35 — dead duplication, not a circular workaround). Only one of the two is a genuine architecture signal.
- **Centrality**: not flagged as a god node in `GRAPH_REPORT.md` ("God Nodes" top-10 lines 215-225 lists no API module). The file appears once in "Surprising Connections" (line 230-231): `update_preferences()` → `isInstance()` in a frontend workbox bundle — a graph-extraction artefact, but indicating `update_preferences` itself was indexed as a notable node. The downstream `User` entity is the **#1 god node with 1019 edges** (line 216), and this file is the principal HTTP surface that mutates `User.password_hash`, `User.email_verified`, `User.two_factor_enabled`, `User.backup_codes`, `User.settings`, `User.preferred_language`, `User.email_verification_token` — i.e. the file is the primary write path into the most-connected entity in the graph. Community 18 (line 315) groups `get_current_active_user`, `get_current_admin_user`, `get_current_user`, "FastAPI dependencies for authentication" and 39 other auth-related nodes — this file is one of two main consumers.

### Couverture tests

- Test file(s) found: `backend/tests/test_auth.py` (533 lines, **35 `def test_` functions**, 7 test classes).
- Approximate coverage estimate: **~25-30% of routes** have at least one happy-path + auth test. Tested routes: `register` (4 cases — success with mocked email, duplicate, invalid email, weak password), `login` (4 — success, wrong pwd, nonexistent, inactive), `refresh` (5 — success, access-token-as-refresh, invalid, expired, inactive), `me` (3), `logout` (2). The remaining 17 tests target `app.security.*` units (encryption 5, JWT 5, dependencies 6) — not endpoints. **14 of the 19 routes have zero endpoint tests**: `update_profile`, `change_password`, `update_preferences`, `get_language_preference`, `update_language_preference`, `delete_account`, **all 7 2FA endpoints** (`verify-login`, `setup`, `enable`, `disable`, `status`, `backup-codes/regenerate`), `verify_email`, `resend_verification`. The 2FA email-OTP path, the auto-login on email verification, and the brute-force IP-block flow are **completely untested**.
- Refactor safety: **risky**.
- Justification: the small core (register, login, refresh, me, logout — ~430 LoC, ~36% of file) is well-tested and would survive an extraction unchanged; but the ~760 LoC of account management, 2FA, and email verification logic — including security-critical paths (backup-code generation, TOTP secret handling, password change, account deletion, brute-force IP-block) — has no characterisation harness. Any decomposition error in the 2FA flow or the email-verification auto-login path would silently weaken authentication guarantees.

### Proposition de découpe

```
backend/app/api/auth/
├── __init__.py             (~10 lines — package marker)
├── router.py               (~50 lines — APIRouter assembly + sub-router include())
├── registration.py         (~180 lines — POST /register, POST /verify-email, POST /resend-verification)
├── login.py                (~220 lines — POST /login, POST /refresh, POST /logout,
│                                       brute-force coordination via app.security.events)
├── two_factor.py           (~340 lines — POST /2fa/verify-login, /2fa/setup, /2fa/enable,
│                                       /2fa/disable, GET /2fa/status, POST /2fa/backup-codes/regenerate)
├── account.py              (~210 lines — GET /me, PUT /me/profile, PUT /me/password,
│                                       PUT /me/preferences, GET/PATCH /me/language, DELETE /me)
└── _email_dispatch.py      (~60 lines — internal helper: build_verification_url(),
                                        send_verification_email(), send_2fa_otp() — collapses
                                        the 3 duplicated send-and-handle-failure blocks)
```

Total ≈ 1070 lines (slight reduction from collapsing the duplicated email-send blocks). The split aligns with the **7 distinct auth flows** identified above and groups by flow rather than by HTTP verb, because each flow has its own state machine (registration → email-verify → login → 2FA-challenge → 2FA-verify) and its own external dependencies (invite tokens, email OTP, TOTP, rate limiter, event logger). Three high-value seams emerge: (a) `_email_dispatch.py` collapses the four duplicated `send_email_verification` / `send_2fa_otp_email` + `(success, error)` blocks at lines 184-198, 308-321, 821-836, 1173-1185 into a single helper used everywhere; (b) `two_factor.py` pulls 330 lines of method-branching out of the file's largest sub-area, making the email-OTP vs TOTP paths individually testable; (c) `login.py` consolidates JWT issuance, brute-force tracking, and security-event logging — the three concerns that today are scattered across `login`, `refresh`, and `verify_2fa_login`. The lazy `InviteToken` import at line 86 stays lazy (genuine relationship-cycle workaround) but moves into `registration.py` where it belongs; the redundant duplicate import of `verify_password` at line 672 disappears entirely. No public URL surface changes — `main.py` continues to mount `auth.router` at `/api/auth/*`.

### Effort & dépendances

- **Effort**: **M**.
- **Justification effort**: ~36% of LoC (register, login, refresh, me, logout) has tests and is a mechanical move; ~64% (account management, 2FA, email verification) requires writing endpoint-level characterisation tests **before** moving, particularly for the 2FA enable/disable/regenerate flow and the email-verification auto-login. Estimated 4-6h: 1h scaffold the sub-package + extract `_email_dispatch.py`, 1h move `login` + `registration` (tested), 2h write characterisation tests for the 7 untested 2FA endpoints + verify-email auto-login + delete-account + change-password + brute-force flow, 2h move `account.py` and `two_factor.py`. No public API URL changes (router prefix `/api/auth` stays in `main.py:158`); the FastAPI `tags=["Authentication"]` annotation may want subdivision (`Authentication`, `2FA`, `Account`, `Email Verification`) which is a separate cosmetic PR.
- **Bloqueurs**: _None._ The file is a leaf in the import DAG; only `main.py` imports it. The lazy `InviteToken` import is a relationship-cycle, not an architecture-cycle, so it does not need to be untangled to ship the split.
- **Bloquant pour**: §A cross-cutting work on (a) the duplicated `EmailService.send_*` / `(success, error)` pattern (also appears in `services/email_service.py` consumers, see §5), (b) the doc/code drift versus `docs/architecture/auth.md`. Splitting this file first lets §A reference a stable target structure when documenting the email-dispatch helper, and the new sub-package becomes the canonical surface to update in `docs/architecture/auth.md` (which today documents only 5 of the 19 endpoints — see §C).
- **Risque**: **medium**.
- **Justification risque**: HTTP contracts are stable and only `main.py` consumes the router; the frontend uses URL paths, not Python imports. However, the 2FA enable / verify-login / regenerate-backup-codes paths mutate `User.two_factor_enabled`, `User.backup_codes`, and `User.totp_secret` with **zero endpoint coverage** — an accidental import-path change or a misplaced commit boundary in the 2FA setup flow could silently weaken backup-code regeneration (e.g. issuing the new codes but failing to persist them, or persisting plaintext instead of hashed). Mitigation: write `test_2fa_endpoints.py` and `test_email_verification_endpoints.py` characterisation tests **before** moving those handlers, and add a security-event-log assertion to confirm side-effect parity.

## §4 — `backend/app/services/email_templates.py` — 841 lines

### Symptômes

Contrairement à ce que le nom suggère, ce fichier n'est **pas** un registre de parseurs d'emails entrants par fournisseur (Netflix, Spotify, etc.) — c'est un générateur de **templates HTML sortants** (résumé d'abonnements, OTP 2FA, vérification d'email). Les trois méthodes publiques produisent chacune un document HTML complet via des f-strings multi-lignes : `generate_summary_email` (lignes 14-266, ~252 lignes), `generate_2fa_otp_email` (lignes 481-658, ~178 lignes), `generate_email_verification_email` (lignes 661-841, ~181 lignes). Chaque méthode embarque sa propre feuille de style CSS dupliquée (corps, conteneur, en-tête en gradient `#667eea → #764ba2`, footer SubTracker, media query mobile à 600px) — environ 60 lignes de CSS quasi-identiques répétées trois fois (lignes 38-194, 502-611, 680-787). Le `summary_email` agrège en plus 7 helpers privés `_render_*` (lignes 269-478) qui produisent des fragments HTML par section (insights, changes, catégories, top subs, AI insights/recos, renewals) avec leur propre style inline. Le résultat est une classe statique de 841 lignes sans état, ~85% HTML/CSS littéral et ~15% logique de rendu, où toute modification de marque (logo, palette, footer) impose une édition triple manuelle.

### Responsabilités identifiées

1. **Template "résumé d'abonnements" (orchestrateur)** (lignes 14-266) — assemble les statistiques utilisateur, les insights, les recommandations IA, les changements, les catégories, les top subs et les renouvellements en un email HTML unique avec CTA vers `/subscriptions`.
2. **Helpers de rendu de fragments du résumé** (lignes 269-478) — 7 fonctions `_render_*` (insights, changes, top_categories, top_subscriptions, ai_insights, ai_recommendations, upcoming_renewals) qui retournent chacune une chaîne HTML ou `""` si données vides ; `_render_upcoming_renewals` importe `datetime` localement (ligne 463) au lieu d'utiliser l'import top-level.
3. **Template "OTP 2FA"** (lignes 481-658) — email transactionnel pour code de vérification à 6 chiffres avec expiration, mises en garde de sécurité, encart "info-box" et "security-notice".
4. **Template "vérification d'email d'inscription"** (lignes 661-841) — email d'onboarding avec bouton CTA `verification_url` (24h d'expiration), lien de secours en texte, message de bienvenue.
5. **Feuille de style commune dupliquée** (lignes 38-194, 502-611, 680-787) — branding SubTracker (gradient header, footer, container 600px, font stack `-apple-system,...`, palette violet `#667eea`/`#764ba2`) répété trois fois sans extraction DRY.

### Couplages (graph-derived)

- **Imports entrants** : 3 sites consommateurs uniquement — `app/services/email_service.py:15` (qui appelle `generate_2fa_otp_email` et `generate_email_verification_email`), et `app/tasks/summary_tasks.py:20` (qui appelle `generate_summary_email` à 2 endroits, lignes 90 et 198). Surface API restreinte → refactor à risque limité.
- **Imports sortants** : seulement `from typing import Dict, Any` au top-level + un `from datetime import datetime` local dans `_render_upcoming_renewals` (ligne 463). Aucun couplage cross-layer (pas de SQLAlchemy, pas de FastAPI, pas de modèles métier) — fichier de présentation pur.
- **Centrality** : _Not flagged in GRAPH_REPORT._ Le rapport ne mentionne pas `email_templates` (`grep` renvoie 0 occurrences sur 4143 nœuds), cohérent avec son rôle de feuille pure consommée par 2 modules.

### Couverture tests

- Test file(s) found: `backend/tests/test_email_templates.py` (561 lignes)
- Approximate coverage estimate: **élevée (~85-95%)** — 4 classes de tests (`TestGenerateSummaryEmail`, `TestGenerate2FAOTPEmail`, `TestGenerateEmailVerificationEmail`, `TestRenderHelpers`) avec 28 cas couvrant chaque méthode publique, chaque helper privé `_render_*`, les chemins vides, les variantes de priorité/pluralisation, le top-5 + reste, les chemins de baisse/hausse de `net_change`.
- Refactor safety: **safe**
- Justification: les assertions testent la présence de fragments textuels (`"Hi {user_name}!"`, `"€49.95"`, `"💡 Key Insights"`) plutôt que la structure HTML exacte ; un découpage en sous-modules qui préserve les noms de méthodes et leur sortie exacte n'invalidera aucune assertion, et la suite tournera quasi-instantanément (pas d'I/O).

### Proposition de découpe

```
backend/app/services/email_templates/
├── __init__.py              (~15 lignes — réexports `EmailTemplates` pour rétro-compat des appelants)
├── _styles.py               (~80 lignes — constantes CSS partagées : BASE_CSS, HEADER_GRADIENT, FOOTER_HTML, render_layout())
├── summary.py               (~280 lignes — generate_summary_email + _render_* helpers, ou split entre summary.py et summary_sections.py)
├── otp_2fa.py               (~180 lignes — generate_2fa_otp_email)
└── verification.py          (~180 lignes — generate_email_verification_email)
```

L'asymétrie du fichier (un gros template orchestré + deux templates standalone) rend le découpe par cas d'usage le plus naturel : chaque sous-module devient indépendamment testable et éditable. Le module `_styles.py` factorise les ~60 lignes de CSS dupliquées trois fois (header gradient, container, footer, font stack, media query 600px) et fournit un helper `render_layout(title, body_html, frontend_url)` qui élimine ~150 lignes de boilerplate. Pour préserver la rétro-compat des deux appelants existants (`email_service.py`, `summary_tasks.py`), `__init__.py` réexporte une classe `EmailTemplates` dont les staticmethods délèguent vers les sous-modules — aucune modification d'appelants requise. Total cible ~735 lignes (vs 841 actuel) grâce à la déduplication CSS.

### Effort & dépendances

- **Effort**: M
- **Justification effort**: découpage mécanique en 4 sous-modules + extraction CSS commun + façade de rétro-compat ; ~3-5h dont 1h pour valider que la suite de tests existante (28 cas) passe sans modification, plus une revue visuelle des emails rendus (Resend dispose d'un mode preview).
- **Bloqueurs**: _None._
- **Bloquant pour**: §5 (`services/email_service.py`) consomme deux des trois templates — un éventuel renommage de méthode impacterait directement l'audit §5 ; conserver les noms `generate_*` exposés via `__init__.py` neutralise ce couplage.
- **Risque**: low
- **Justification risque**: fichier sans état, sans I/O, sans dépendance ORM/HTTP ; surface API étroite (3 méthodes publiques, 2 consommateurs) ; couverture de tests élevée et orientée comportement ; régressions visuelles détectables par diff HTML automatisé sur fixtures.

> **Note pour §5 et §A** : `email_service.py` (782 lignes, prochain audit) **délègue** la génération HTML à `email_templates.py` — pas de duplication, l'overlap est une dépendance saine (un layer "delivery" Resend + un layer "rendering"). En revanche, l'asymétrie est suspecte : `email_service.py` envoie probablement aussi d'autres types d'emails (price change, renewal reminder, trial reminder, budget alert, system announcement — à confirmer en §5) qui pourraient générer leur HTML en ligne plutôt que via `EmailTemplates`. Si c'est le cas, §A devrait flagger une **incohérence d'extraction** : seuls 3 templates sont externalisés ici, les autres restant inline dans `email_service.py`. Pattern cross-cutting déjà observé en §3 (auth.py contient lui aussi des helpers d'envoi d'email — voir §3 ligne 233).

## §5 — `backend/app/services/email_service.py` — 782 lines

### Symptômes

Ce module est annoncé comme « service de livraison Resend » (docstring l.2) mais ~63% de son volume (lignes 287-778, soit ~490 lignes sur 782) est en réalité du **HTML/CSS littéral** dans trois templates inline (`_get_renewal_reminder_template`, `_get_weekly_summary_template`, `_get_monthly_summary_template`). Le module mélange donc trois rôles : configuration du transport Resend, méthodes typées par cas d'usage (6 wrappers `send_*`), et rendu HTML inline pour 3 d'entre eux. La cohabitation est **incohérente** : `send_2fa_otp_email` (l.221) et `send_email_verification` (l.261) délèguent proprement à `EmailTemplates.generate_*`, alors que `send_renewal_reminder`, `send_weekly_summary` et `send_monthly_summary` conservent leur HTML dans le service. Pire, l'inspection des call-sites révèle que **les wrappers typés `send_renewal_reminder` / `send_weekly_summary` / `send_monthly_summary` sont quasiment morts en production** : `summary_tasks.py:90,95,198,203` rend lui-même via `EmailTemplates.generate_summary_email()` puis appelle `email_service.send_email()` (transport brut), seul `notification_service.py:118,136,145` utilise les wrappers typés. Une instance singleton `email_service = EmailService()` (l.782) est créée au chargement du module, ce qui empêche tout accès à un `db: Session` au moment de l'init et neutralise partiellement la valeur du paramètre `db` du constructeur.

### Responsabilités identifiées

1. **Configuration du transport Resend** (lignes 23-42) — lecture clé API et headers `from` via `get_config_value`, configuration globale `resend.api_key`.
2. **Envoi générique** (lignes 44-86) — `send_email(to, subject, html, plain)` qui retourne `(success, error)`, journalisation et capture d'exception.
3. **Wrappers typés par cas d'usage** (lignes 88-285) — 5 méthodes `send_renewal_reminder`, `send_weekly_summary`, `send_monthly_summary`, `send_2fa_otp_email`, `send_email_verification` qui composent sujet + texte plain + appel au templater + délégation à `send_email`.
4. **Rendu HTML inline pour 3 emails** (lignes 287-778) — `_get_renewal_reminder_template`, `_get_weekly_summary_template`, `_get_monthly_summary_template` : ~490 lignes de HTML/CSS f-string avec gradients, layouts et logique de tri/filtrage embarquée (`sorted(...)[:10]`, `subscriptions[:5]`, calcul de `diff_percent`).
5. **Singleton de module** (ligne 782) — `email_service = EmailService()` instancié à l'import, sans `db` fourni, donc `get_config_value` retombe systématiquement sur les variables d'env.

### Couplages (graph-derived)

- **Imports entrants**: 8 importateurs identifiés (`grep -rln 'from app.services.email_service'`):
  - `app/tasks/budget_alerts.py`, `app/tasks/renewal_reminders.py`, `app/tasks/trial_reminders.py`, `app/tasks/summary_tasks.py`, `app/tasks/system_announcements.py`, `app/tasks/price_change_monitor.py` (tous via `email_service.send_email(...)` brut)
  - `app/api/auth.py` (via `send_2fa_otp_email`, `send_email_verification` aux lignes 185, 310, 823, 1176)
  - `app/services/notification_service.py` (seul caller des wrappers `send_renewal_reminder` / `send_weekly_summary` / `send_monthly_summary`)
- **Imports sortants**: `resend`, `sqlalchemy.orm.Session`, `app.config.settings`, `app.utils.config_helper.get_config_value`, `app.services.email_templates.EmailTemplates`. Pas de fuite cross-layer (aucun import de `app.models.*` ou `app.api.*`). **Relation avec `email_templates.py` (§4)** : `EmailTemplates` est importé mais utilisé seulement par 2 méthodes sur 5 — l'inverse est aussi vrai côté `email_templates.py` (`generate_summary_email` n'est jamais appelée par `email_service` mais directement par `summary_tasks.py`). Frontière de responsabilité **floue et inconsistante** entre les deux modules.
- **Centrality**: _Not flagged in GRAPH_REPORT.md_ (le grep ne renvoie aucune occurrence du fichier dans le rapport graphify), mais le fan-in de 8 importateurs et la position de hub de notification suggèrent un god-node de fait pour la couche notifications.

### Couverture tests

- Test file(s) found: aucun `test_email_service.py` direct dans `backend/tests/` (un `test_email_service.cpython-311-pytest-7.4.4.pyc` traîne dans `__pycache__/` → fichier source supprimé sans nettoyage du cache). Couverture indirecte via : `test_renewal_reminders.py`, `test_summary_tasks.py`, `test_trial_reminders.py`, `test_budget_alerts.py`, `test_system_announcements.py`, `test_price_change_monitor.py`, `test_email_verification.py`, `test_email_templates.py`.
- Approximate coverage estimate: ~30-40% — le transport `send_email` et la délégation `send_2fa_otp_email`/`send_email_verification` sont probablement mockés dans les tests amont, mais les 3 templates HTML inline et les wrappers typés (`send_renewal_reminder`, `send_weekly_summary`, `send_monthly_summary`) n'ont aucune assertion de rendu directe.
- Refactor safety: **risky**.
- Justification: l'absence de test direct + le fan-in de 8 importateurs + le singleton de module rendent toute extraction des templates inline détectable uniquement à l'exécution ; un test de non-régression sur le HTML rendu (snapshot) est un préalable obligatoire.

### Proposition de découpe

```
backend/app/services/
├── email/
│   ├── __init__.py
│   ├── transport.py              # EmailService (Resend wrapper, send_email seul)
│   └── templates/                # restructuration de §4 + extraction inline
│       ├── __init__.py
│       ├── base.py               # layout/CSS partagés (extraction des duplications)
│       ├── otp_2fa.py            # déjà dans email_templates.py (§4)
│       ├── verification.py       # déjà dans email_templates.py (§4)
│       ├── summary.py            # déjà dans email_templates.py (§4)
│       ├── renewal_reminder.py   # extrait de email_service.py l.287-424
│       ├── weekly_summary.py     # extrait de email_service.py l.426-596
│       └── monthly_summary.py    # extrait de email_service.py l.598-778
```

Cette découpe **fusionne** le rôle « rendu » dans un package `email_templates/` étendu (cf. proposition §4) et réduit `email_service.py` à un transport pur (~80 lignes : `send_email` + config). Les 5 wrappers typés `send_*_reminder/summary` sont à **supprimer** : `notification_service.py` (seul caller) doit être migré vers le pattern déjà utilisé par `summary_tasks.py` (rendu via `EmailTemplates.*` puis `transport.send_email`). Justification : aujourd'hui le rendu HTML est dupliqué entre `email_service.py` (3 templates), `email_templates.py` (3 templates) et **5 fichiers `tasks/*` qui contiennent chacun 7 à 11 occurrences de balises HTML** (`grep` confirme : 8/11/8/11/7 pour renewal/trial/system/price/budget) — l'unification dans `services/email/templates/` est donc un gain transversal, pas seulement local à ce fichier.

### Effort & dépendances

- **Effort**: M
- **Justification effort**: 3 templates à extraire (~490 lignes de HTML purement déplaçables), 5 wrappers typés à supprimer + 3 call-sites dans `notification_service.py` à migrer, restructuration cohérente avec §4 (effort partiellement mutualisé). Pas de logique métier à réécrire. Estimation 4-6h incluant snapshot tests préalables.
- **Bloqueurs**: refactor §4 (`email_templates.py`) à mener en même temps ou en amont pour éviter un état intermédiaire fragmenté.
- **Bloquant pour**: extraction des HTML inline présents dans `tasks/budget_alerts.py`, `tasks/renewal_reminders.py`, `tasks/trial_reminders.py`, `tasks/system_announcements.py`, `tasks/price_change_monitor.py` (5 fichiers, à traiter en §A après consolidation du package templates).
- **Risque**: medium
- **Justification risque**: aucun test direct du module + singleton de module + 8 importateurs ; mitigation = snapshot tests sur les 3 templates HTML avant extraction et tests d'intégration mockés sur `send_email` pour préserver la signature `(bool, Optional[str])`.

## §A — Constats transverses

Cette section synthétise les patterns observés à travers §1-§5 qui touchent au moins deux des cinq fichiers audités. Six constats émergent. Chacun nomme un **goulot structurel** (axe A.1, A.3) ou une **dette de duplication** (A.2, A.4) qui contraint l'ordre d'exécution du refactor C1 : trois d'entre eux (A.1, A.2, A.4) imposent de livrer un module partagé **avant** d'extraire les fichiers individuels, sous peine de figer la duplication dans la nouvelle arborescence.

### A.1 — Triangle structurellement circulaire `api ↔ tasks ↔ services`

- **Fichiers concernés**: §1 (`api/subscriptions.py:783, :1045`), §2 (`tasks/email_sync.py:156, :157, :487`), §3 (`api/auth.py:86`) — plus le caller hors-périmètre `api/mailboxes.py:355, :474`.
- **Constat**: 8 imports intra-fonction « paresseux » (dont 7 architecturalement signifiants ; le 8e à `auth.py:672` est un duplicat mort de `verify_password` déjà importé en haut, et celui de `email_templates.py:463` n'importe que `datetime`) tracent un triangle de dépendance circulaire entre les trois couches : la couche `api` réintègre du code de `tasks` (`update_subscription_statuses`, `sync_mailbox_emails`) et de `services` (`renewal_calculator`, `invite_token` model), tandis que `tasks/email_sync` réintègre 3 services AI (`ai_classifier`, `subscription_extractor`, `reference_extractor`) — qui consomment eux-mêmes les modèles ORM partagés. Le fait remarquable est que **chaque caller de `email_sync` en production utilise un import paresseux** (`api/mailboxes.py` × 2, `api/subscriptions.py` × 1) : c'est le diagnostic, pas l'exception. Aucun import top-level cross-layer (`grep -rE '^from app\.(api|tasks)' services/ tasks/` renvoie zéro résultat) — toute la circularité est résolue par des imports de fonction.
- **Impact pour C1**: contraint l'ordre du refactor. Extraire `tasks/email_sync.py` en premier sans introduire d'interface seam (un `app/services/email_pipeline_protocol.py` ou similaire) ne ferait que **déplacer** les imports paresseux vers les nouveaux sous-modules. Le découpage de §2 doit donc soit (a) introduire un module de types/protocoles partagés que `api`, `tasks` et les services AI peuvent importer sans cycle, soit (b) basculer les services AI en injection de dépendances (passés en argument à `_sync_mailbox_async` au lieu d'importés) — ce qui les rend aussi mockables et résout incidemment la mauvaise testabilité du pipeline interne (§2 «~600 lignes non testées»). Sans cette étape préalable, le split de §2 figerait les 3 imports paresseux dans `stages/classification.py` et `stages/extraction.py`.

### A.2 — Logique métier dupliquée par absence d'utilitaires partagés

- **Fichiers concernés**: §1 (`api/subscriptions.py:207-217, :229-236, :327-338, :436-507, :595-599, :1406-1411`), §2 (`tasks/email_sync.py:374-394, :602-625, :647-661, :441-576, :298-302, :401-408, :420-427, :772-799`), §3 (`api/auth.py:184-198, :308-321, :821-836, :1173-1185`).
- **Constat**: **trois axes de duplication métier** convergent vers la même cause racine — l'absence de couche utilitaire partagée entre les couches `api` et `tasks`. (a) **Projection de coût d'abonnement** (formules `amount * 12`, `amount / 12`, `amount * 4.33`, `amount / 3`, `amount / 6`) répétée 3 fois dans `api/subscriptions.py` (stats, analytics-trends × 2). (b) **Arithmétique de variation de prix** (`(new - old) / old * 100`, classification `"increase"/"decrease"`, instanciation `PriceHistory`) répétée 3 fois dans `tasks/email_sync.py` (path AI-flagged, post-hoc, initial). (c) **Politique de déduplication** : §1 encode 71 lignes de scoring heuristique dans `find_duplicate_subscriptions` (sender similarity, fuzzy provider match, amount ±5%, billing cycle, period) ; §2 encode 115 lignes de stratégie multi-niveau (service references → email_sender → custom_label keywords → fallback) avec une liste hardcodée de payment processors (`paypal/stripe/paddle/gumroad/fastspring`). Les deux fichiers manipulent aussi la table d'association `subscription_emails` en SQL brut (13 hits dans §1, 5 hits dans §2) sans jamais passer par la relation ORM `Subscription.emails`. (d) **Boilerplate d'envoi d'email auth** : le bloc `EmailService(db).send_*` + déballage `(success, error)` + `raise HTTPException(500, "...try resending")` est dupliqué 4 fois dans `api/auth.py` (register, login OTP, 2FA setup, resend-verification).
- **Impact pour C1**: bloque § B sur la séquence des PR. Trois utilitaires partagés doivent être extraits **avant** de splitter §1 et §2 — sinon chaque sous-module hérite de sa copie locale et le gain de DRY est perdu :
  - `app/services/cost_projection.py` (~40 lignes) consommé par les futurs `api/subscriptions/stats.py` et `analytics.py`.
  - `app/services/price_history_recorder.py` (~90 lignes, mentionné dans §2 «Bloquant pour») consommé par les futurs `tasks/email_sync/price_history.py` et `api/subscriptions/merge_split.py`.
  - `app/services/dedup_strategy.py` (consolide les 71+115 lignes ; mentionné dans §2) consommé par `api/subscriptions/duplicates.py` et `tasks/email_sync/persistence.py`.
  - `app/api/auth/_email_dispatch.py` (helper interne de §3, ~60 lignes) collapse les 4 blocs identiques.

### A.3 — Responsabilités co-localisées hors-couche dans chaque fichier

- **Fichiers concernés**: les cinq — §1 (API qui fait du repository : raw SQL `subscription_emails.update()` aux lignes 597 et 1407), §2 (tâche Celery qui fait du pipeline d'extraction : `_sync_mailbox_async` 820 lignes mêlant transport, classification, extraction, dedup, persistence, progress tracking), §3 (API qui pilote 5 sous-modules `app.security.*` directement : `TOTPManager`, `EmailOTPManager`, `BackupCodesManager`, `VerificationRateLimiter`, `events` — au lieu d'une façade `TwoFactorAuth`), §4 (template HTML qui embarque sa propre CSS dupliquée 3 fois : pas un mélange de couches mais un mélange de préoccupations — layout / styles / sections), §5 (transport Resend + 5 wrappers typés + 3 templates HTML inline + singleton de module).
- **Constat**: chaque fichier audité co-localise au moins **deux préoccupations** qui devraient vivre dans des couches distinctes. Le cas le plus aigu est §2 (orchestrateur de 820 lignes regroupant 8 stages numérotés en commentaires `# STAGE 1/2/3` mais jamais réifiés en modules) ; le plus structurel est §1 (couche API qui shunte la relation ORM pour écrire directement dans la table d'association — empêchant tout test contractuel via `Subscription.emails`) ; le plus systémique est §3 (la façade `TwoFactorAuth` existe dans `app.security.two_factor` mais l'API importe les 3 managers séparément, l'abstraction fuit donc à chaque endpoint 2FA).
- **Impact pour C1**: justifie le **regroupement par flow** plutôt que par verbe HTTP dans les propositions de découpe (§1, §3) et le **regroupement par stage de pipeline** dans §2. Un sous-bénéfice : chaque seam ainsi exposé devient un point d'injection naturel pour les tests de caractérisation manquants (cf. A.5). Surtout, §3 invite à fermer la fuite d'abstraction `TwoFactorAuth` **dans le même PR** que le split du fichier — sans quoi `api/auth/two_factor.py` continuera d'importer 3 managers séparés et le découpage n'apporte aucun gain de couplage.

### A.4 — Frontière `rendering` / `delivery` incohérente pour les emails sortants

- **Fichiers concernés**: §4 (`services/email_templates.py` — 3 templates externalisés), §5 (`services/email_service.py:287-778` — 3 templates inline) ; plus 5 tâches Celery hors-périmètre qui mêlent rendu HTML et envoi : `tasks/budget_alerts.py` (8 balises HTML), `tasks/renewal_reminders.py` (10), `tasks/trial_reminders.py` (13), `tasks/system_announcements.py` (10), `tasks/price_change_monitor.py` (13).
- **Constat**: la division entre « rendu HTML » et « delivery Resend » est implémentée à moitié. `email_templates.py` héberge 3 templates (`generate_summary_email`, `generate_2fa_otp_email`, `generate_email_verification_email`), mais `email_service.py` héberge **3 templates supplémentaires inline** (`_get_renewal_reminder_template`, `_get_weekly_summary_template`, `_get_monthly_summary_template`) qui représentent ~63% du volume du fichier (490 lignes sur 782) — soit autant de HTML que dans `email_templates.py` lui-même. Pire, les 5 tâches Celery périphériques rendent leur HTML **directement dans le code de tâche** au lieu d'utiliser `EmailTemplates`, ajoutant ~54 occurrences de balises HTML cumulées sur 5 fichiers. Et la même CSS de marque (gradient `#667eea → #764ba2`, container 600px, footer SubTracker, font stack) est dupliquée à travers tous ces sites — au moins 8 copies non-DRY sans compter §4 (qui en contient déjà 3 internes).
- **Impact pour C1**: §4 et §5 doivent être refactorés **ensemble** (et non pas dans deux PR séparés) sous peine de figer un état intermédiaire encore plus fragmenté. La proposition consolidée (§5) — un package `services/email/templates/` qui absorbe à la fois les 3 templates de §4, les 3 templates inline de §5, **et** les rendus inline des 5 tâches périphériques — est un travail transversal qui prolonge le périmètre C1. Le singleton `email_service = EmailService()` (cf. A.6) doit aussi disparaître dans le même mouvement, sinon la séparation `transport` / `templates` reste polluée par un objet stateful global.

### A.5 — Tests de caractérisation manquants sur les chemins mutation-critiques

- **Fichiers concernés**: §1 (6 routes mutationnelles non testées : `find_duplicate_subscriptions`, `merge_subscriptions`, `update_subscription_renewal_status`, `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion`, `split_subscription`), §2 (~600 lignes du pipeline interne non couvertes : multi-strategy dedup, 3 paths price-history, renewal step, cancellation suggestion, polling de cancellation, écritures association-table), §3 (14 routes sur 19 sans test endpoint : 2FA × 7, account management × 6, email verification × 1).
- **Constat**: c'est le **même pattern dans les trois fichiers** — la coquille externe est testée (CRUD basique, login, refresh, helpers isolés), mais les chemins mutation-critiques sont laissés sans harness. Et ce n'est pas du hasard : les 600 lignes non testées de §2 correspondent à la même surface (subscription-mutating) que les 6 routes non testées de §1 (merge, split, renewal-reconciliation), via la fonction partagée `update_subscription_statuses` exportée depuis §2 vers §1 (§1 ligne 783). Les 7 endpoints 2FA non testés de §3 mutent `User.two_factor_enabled`, `User.backup_codes`, `User.totp_secret` — soit les champs les plus security-critical du #1 god-node graph (`User`, 1019 edges).
- **Impact pour C1**: tests de caractérisation = **prérequis**, pas optionnel. Le plan §B doit séquencer **« écrire tests → splitter »** pour §1, §2 et §3, sans chevauchement. Mitigation pratique : pour §2 spécifiquement, le risque de hisser un `db.commit()` hors de la portée per-email exige un fixture qui compte les commits/rollbacks pour vérifier la parité transactionnelle (§2 «Mitigation»). Pour §1/§3, des tests de réponse + assertions sur side-effects de DB et de security-event log suffisent. Cette dette de test représente l'essentiel de l'effort `L` de §2 (12-16h estimées dont 4h dédiées aux characterisation tests) et la moitié de l'effort `M` de §1 et §3.

### A.6 — Singletons de module et fuite de configuration

- **Fichiers concernés**: §5 (`services/email_service.py:782` — `email_service = EmailService()`) ; pattern observé aussi dans `services/push_notification_service.py:171` (hors périmètre, mais atteste que c'est récurrent côté services).
- **Constat**: l'instanciation au niveau du module se fait **sans `db: Session`**, ce qui force `EmailService.__init__` à toujours retomber sur `get_config_value(..., db=None)` — donc sur les variables d'environnement, jamais sur la table `app_config`. Le paramètre `db` du constructeur, prévu pour permettre une lecture per-tenant de la config Resend (`from`-headers, signing domain), est de fait neutralisé dès l'import. Les 8 importateurs (`tasks/budget_alerts.py`, `tasks/renewal_reminders.py`, `tasks/trial_reminders.py`, `tasks/summary_tasks.py`, `tasks/system_announcements.py`, `tasks/price_change_monitor.py`, `api/auth.py`, `services/notification_service.py`) consomment tous le singleton — donc aucun ne peut bénéficier d'une config DB-driven.
- **Impact pour C1**: bloque la séparation `transport` / `templates` proposée en §5. Avant de splitter §5, il faut soit (a) supprimer le singleton et laisser chaque caller faire `EmailService(db)` (acceptable si les 8 sites passent déjà un `db`), soit (b) introduire un factory `get_email_service(db: Session)` qui retourne une instance per-request. L'option (a) est plus simple si les call-sites le permettent ; sinon (b) impose une mini-migration des 8 sites avant le split. Ce point n'est pas bloquant pour §1-§4 mais doit être tranché dans le PR qui exécute §5.

## §B — Roadmap priorisée

Cette section ordonne le sous-projet C1 en **5 phases** dérivées des §1-§5 (effort × risque × impact) et contraintes par §A. La **Phase 0** livre les pré-conditions (4 modules partagés + tests de caractérisation) qui débloquent toutes les phases suivantes ; la **Phase 1** traite §4+§5 ensemble (couplage imposé par A.4) ; les **Phases 2-4** traitent §1, §3, §2 dans cet ordre — §2 en dernier car c'est le seul XL+high-risk du lot et il bénéficie d'avoir `dedup_strategy.py` et `price_history_recorder.py` déjà éprouvés par les phases précédentes.

> **Phase 0 débloque toutes les phases suivantes — ne pas la sauter.** Une exécution partielle (par ex. shipper les 4 modules sans les chartests, ou inversement) invalide le filet de sécurité et fige la duplication dans la nouvelle arborescence.

### Phase 0 — Pre-conditions (modules partagés + tests de caractérisation)

- **Fichiers affectés**: NOUVEAUX — `backend/app/services/cost_projection.py`, `backend/app/services/price_history_recorder.py`, `backend/app/services/dedup_strategy.py`, `backend/app/api/_email_dispatch.py`. Plus tests dans `backend/tests/` (chartests pour les 6 routes non testées de §1, l'inner-pipeline de §2, les 14 routes non testées de §3).
- **Pourquoi en premier**: §A.2 (logique métier dupliquée) et §A.5 (chemins mutation non testés) **gatent toutes** les phases per-fichier. Sans Phase 0, chaque extraction soit (a) ship la duplication dans la nouvelle arborescence — annulant le gain DRY — soit (b) risque une régression silencieuse sur des chemins write-path non couverts (mutations `User`, `Subscription`, association-table, backup codes 2FA).
- **Effort**: **M-L** — décomposé : `cost_projection.py` (S, ~40 lignes, extraction triplicate de §1:207-217, :229-236, :327-338) + `price_history_recorder.py` (M, ~90 lignes, consolidation des 3 paths de §2:374-394, :602-625, :647-661) + `dedup_strategy.py` (M, ~186 lignes consolidées de §1:436-507 + §2:441-576 incluant la liste `paypal/stripe/paddle/gumroad/fastspring`) + `_email_dispatch.py` (S, ~60 lignes, collapse les 4 sites de §3:184-198, :308-321, :821-836, :1173-1185) + chartests (M, principal coût). Estimation 8-12h.
- **Risque**: **low** — toutes les modifications sont additives : nouveaux modules + nouveaux tests, aucun changement de contrat HTTP ni de signature publique. Les chartests *capturent* le comportement actuel sans le modifier.
- **Dépendances**: _Aucune._ Cette phase est indépendante et peut démarrer immédiatement.
- **Concrets**:
  1. `cost_projection.py` (S) — fonction pure `project_monthly_cost(amount, billing_cycle)` + variantes yearly/weekly. Extraction mécanique des 3 sites de §1.
  2. `price_history_recorder.py` (M) — exposera `record_price_update`, `record_initial_price`, `record_price_change` couvrant les 3 paths inline de §2. Sera réutilisé par `api/subscriptions/merge_split.py` (Phase 2).
  3. `dedup_strategy.py` (M) — consolide la stratégie multi-niveau de §2 (service-reference → email_sender → custom_label → fallback) et le scoring heuristique de §1 (`find_duplicate_subscriptions`). Surface API : `score_duplicate_pair`, `find_best_match`. Devient le point d'injection naturel quand service-reference matching maturera.
  4. `_email_dispatch.py` (S) — helper interne avec `build_verification_url`, `send_verification_email`, `send_2fa_otp` qui encapsulent `EmailService(db).send_*` + déballage `(success, error)` + `HTTPException(500)`. Élimine les 4 duplications de §3.
  5. **Chartests** (M, le gros du coût) — séquence obligatoire avant Phases 2/3/4 :
     - 6 chartests pour §1 : `merge_subscriptions`, `split_subscription`, `find_duplicate_subscriptions`, `update_subscription_renewal_status`, `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion` (assertions sur side-effects DB + association-table).
     - Chartests pour l'inner-pipeline de §2 : multi-strategy dedup, 3 paths price-history, renewal step, cancellation step, polling de cancellation, écritures `subscription_emails`. Inclure un fixture qui compte `db.commit()`/`db.rollback()` pour parité transactionnelle (cf. §2 «Mitigation»).
     - Chartests pour §3 : les 7 endpoints 2FA (mutent `User.totp_secret`, `User.backup_codes`, `User.two_factor_enabled`), `verify_email` auto-login, `delete_account`, `change_password`, `update_preferences` — avec assertions sur les security-event logs.

### Phase 1 — Refactor consolidé `services/email/` (§4 + §5)

- **Fichiers affectés**: §4 (`services/email_templates.py`) + §5 (`services/email_service.py`).
- **Pourquoi avant les API** : §A.4 impose le couplage §4↔§5 (les frontières rendering/delivery sont incohérentes : 3 templates externalisés dans §4 + 3 templates inline dans §5 + ~54 balises HTML dans 5 tâches Celery périphériques). Composite le plus élevé du lot (§4=7 low-risk, §5=6 medium-risk) avec le risque le plus faible une fois §4 terminé : §4 a une couverture de tests de **~90%** (28 tests behavior-based) et zéro fuite cross-layer. Shippé en premier, §4 valide le pattern de découpage par cas d'usage avant que les phases plus risquées n'attaquent §1/§2/§3.
- **Effort**: **M+M = ~M-L** (~7-11h dont snapshot tests préalables sur les 3 templates inline de §5 + migration des 3 call-sites de `notification_service.py` + dissolution du singleton `email_service` per A.6).
- **Risque**: **low → medium** — §4 est safe (tests behavior-based, aucun couplage cross-layer) ; §5 est medium (8 importateurs, singleton de module à désactiver, aucun test direct de `email_service.py`). Mitigation : snapshot tests HTML sur les 3 templates inline avant extraction.
- **Dépendances**: Phase 0 (caractérisation tests pour les chemins concernés ne sont pas critiques ici, mais Phase 0 doit être complète pour ne pas bloquer la suite).
- **Concrets**:
  1. Restructurer `services/email_templates.py` en package `services/email/templates/` avec `_styles.py` (factorise CSS dupliquée 3×), `summary.py`, `otp_2fa.py`, `verification.py`. Façade `EmailTemplates` réexportée depuis `__init__.py` pour rétro-compat.
  2. Extraire les 3 templates inline de `email_service.py:287-778` vers `services/email/templates/{renewal_reminder,weekly_summary,monthly_summary}.py`.
  3. Réduire `email_service.py` à `services/email/transport.py` (~80 lignes : `send_email` + config Resend uniquement). Supprimer les 5 wrappers typés morts (`send_renewal_reminder`, `send_weekly_summary`, `send_monthly_summary`).
  4. Migrer `notification_service.py:118, :136, :145` (seul caller des wrappers supprimés) vers le pattern `EmailTemplates.* + transport.send_email`.
  5. **Dissoudre le singleton `email_service = EmailService()`** (per A.6) : soit supprimer et exiger `EmailService(db)` aux 8 sites, soit introduire un factory `get_email_service(db)`. Trancher dans ce PR.
  6. **Hors-scope explicite mais flaggé pour §C** : les ~54 balises HTML inline dans `tasks/{budget_alerts,renewal_reminders,trial_reminders,system_announcements,price_change_monitor}.py` constituent une extension naturelle après Phase 1, à traiter en C2.

### Phase 2 — Refactor `api/subscriptions/` (§1)

- **Fichiers affectés**: §1 (`api/subscriptions.py` → `api/subscriptions/{router,crud,stats,analytics,duplicates,merge_split,status_reconcile,feedback,price_history,cancellation_suggestion}.py`).
- **Pourquoi maintenant**: composite 7 (medium risk après chartests). §1 consomme **3 des 4 modules livrés en Phase 0** (`cost_projection`, `dedup_strategy`, `price_history_recorder` via merge), donc shipper §1 avant §2 valide ces modules sur la surface la plus testée (CRUD/stats/analytics ont déjà ~65% de couverture). §1 est aussi un leaf de l'import-DAG (seul `main.py` l'importe, §1 lignes 40, 195) : zéro risque de régression cross-module en dehors du sous-package lui-même.
- **Effort**: **M** (~4-6h, conforme à §1) — 60% mécanique grâce à la couverture existante ; les 6 routes mutationnelles déjà couvertes par les chartests de Phase 0.
- **Risque**: **medium** — les chemins merge/split mutent `subscription_emails` en SQL brut, mais sont désormais protégés par les chartests de Phase 0. Les helpers `cost_projection`, `dedup_strategy`, `price_history_recorder` étant testés indépendamment en Phase 0, leur intégration ici est mécanique.
- **Dépendances**: **Phase 0 complète** (les 3 modules partagés + les 6 chartests sont obligatoires).
- **Concrets**:
  1. Scaffold `api/subscriptions/` selon découpe §1.
  2. Déplacer les endpoints CRUD/stats/analytics/duplicates testés (~60% du LoC) — guarantie par `test_subscriptions_api.py:40 tests`.
  3. Câbler `cost_projection.project_monthly_cost` dans `stats.py` et `analytics.py` (élimine les 3 duplications).
  4. Câbler `dedup_strategy.score_duplicate_pair` dans `duplicates.py` (élimine les 71 lignes de scoring inline).
  5. Câbler `price_history_recorder` dans `merge_split.py` (consistance avec §2 Phase 4).
  6. Déplacer `merge_subscriptions` et `split_subscription` (chartests Phase 0 servent de filet).
  7. Collapse les 2 imports paresseux de §1:783 (`update_subscription_statuses`) et §1:1045 (`RenewalCalculator`) en imports module-level dans `status_reconcile.py` — cycle non concerné, c'est un faux-positif (cf. A.1).

### Phase 3 — Refactor `api/auth/` (§3)

- **Fichiers affectés**: §3 (`api/auth.py` → `api/auth/{router,registration,login,two_factor,account,_email_dispatch}.py`).
- **Pourquoi après §1**: composite 7, mais risque medium concentré sur des paths security-critical (2FA, password change, email verification auto-login) tous mutant le god-node `User` (1019 edges). §1 sert de répétition générale (split d'un router de taille comparable, leaf du DAG, helpers consommés depuis Phase 0). `_email_dispatch.py` étant déjà livré en Phase 0, il ne reste que la mécanique de découpage et la fermeture de la fuite d'abstraction `TwoFactorAuth` (per A.3).
- **Effort**: **M** (~4-6h, conforme à §3).
- **Risque**: **medium** — security-critical mais protégé par les 14 chartests endpoint de Phase 0 (notamment les 7 chartests 2FA + auto-login email-verification + delete_account + change_password). Mitigation supplémentaire : assertions sur les security-event logs dans chaque chartest pour parité side-effects.
- **Dépendances**: **Phase 0 complète** (`_email_dispatch.py` + chartests endpoint 2FA/account/email-verification).
- **Concrets**:
  1. Scaffold `api/auth/` selon découpe §3.
  2. Déplacer registration / login / refresh / me / logout (déjà couverts par les 35 tests existants).
  3. Câbler `_email_dispatch.py` à 4 sites : `register`, `login` OTP, `2fa/setup`, `resend-verification` (collapse de 4 blocs identiques en 1 helper, gain ~50 lignes nettes).
  4. Déplacer les 7 endpoints 2FA dans `two_factor.py` (chartests Phase 0 servent de filet).
  5. **Fermer la fuite d'abstraction `TwoFactorAuth`** (per A.3) : `two_factor.py` doit importer **uniquement** `TwoFactorAuth` depuis `app.security.two_factor`, pas les 3 managers séparés (`TOTPManager`, `EmailOTPManager`, `BackupCodesManager`). Sans cette étape, le découpage n'apporte aucun gain de couplage.
  6. Supprimer le duplicat mort `from app.security.password import verify_password` à §3:672 (déjà importé en haut, ligne 35).
  7. La double système de préférences "language" (§3 lignes 562-652 : JSONB `settings` + colonne dédiée `preferred_language`) est notée pour §C — pas tranchée dans cette phase.

### Phase 4 — Refactor `tasks/email_sync/` (§2)

- **Fichiers affectés**: §2 (`tasks/email_sync.py` → `tasks/email_sync/{celery_tasks,orchestrator,stages/*,dedup_strategy,price_history,renewal_step,cancellation_step,progress_tracker,filters,status_reconciler}.py`).
- **Pourquoi en dernier**: composite 6 — seul L+high-risk du lot. Doit absorber les 4 contraintes les plus lourdes de §A simultanément : (A.1) introduire l'interface seam pour briser le triangle `api ↔ tasks ↔ services` ; (A.2) consommer `dedup_strategy.py` + `price_history_recorder.py` (livrés Phase 0, validés Phase 2) ; (A.3) réifier les 3 stages déjà commentés dans le code mais jamais modulés ; (A.5) survivre à 600 lignes de business logic non testée *même après* les chartests de Phase 0 (qui couvrent les chemins critiques mais pas les 100%). Faire §2 en dernier maximise le ROI des phases précédentes : `dedup_strategy.py` aura traversé deux refactors avant d'arriver ici, donc aura absorbé les corner-cases.
- **Effort**: **L** (~12-16h, conforme à §2) — dont 4h pour les chartests *additionnels* sur les paths les plus exotiques (commit boundaries, `db.refresh(mailbox)` cancellation polling, association-table writes) qui ne sont pas tous couverts par Phase 0.
- **Risque**: **high** — code on the data-write path pour les 4 entités les plus connectées du graphe (`Subscription` 816 edges, `Mailbox` 305, `PriceHistory` 148, `EmailMessage` 136). Le 5-level-deep `try/except` + commits per-email implicites veulent dire qu'**hisser un commit hors de la per-email scope batch-corromp les semantics rollback**. Mitigation : chartests Phase 0 + fixture qui compte commits/rollbacks + tests de cancellation end-to-end (envoyer un cancellation request mid-batch et asserter que les subs déjà persistés survivent et que les en-cours sont rollbackés).
- **Dépendances**: **Phase 0 complète** + **Phase 2** (valide que `dedup_strategy.py` et `price_history_recorder.py` fonctionnent dans un contexte de production).
- **Concrets**:
  1. **Introduire l'interface seam** (résout A.1) : créer `app/services/email_pipeline_protocol.py` qui définit les Protocols pour `AIClassifier`, `SubscriptionExtractor`, `ReferenceExtractor`. `_sync_mailbox_async` accepte ces protocols **par injection** au lieu de les importer paresseusement à §2:156-157, :487. Bénéfice secondaire : la pipeline interne devient mockable, débloquant les tests des 600 lignes non couvertes.
  2. Scaffold `tasks/email_sync/` selon découpe §2, avec `__init__.py` qui réexporte `sync_mailbox_emails`, `check_scheduled_syncs`, `update_subscription_statuses`, `parse_date_filter` pour rétro-compat des 3 callers (`api/mailboxes.py`, `api/subscriptions.py`, `tests/test_email_sync.py`).
  3. Déplacer les helpers testés en premier : `parse_date_filter`, `update_subscription_statuses`, `DatabaseTask`, `filter_subscription_data`.
  4. Câbler `dedup_strategy.py` (Phase 0) dans `stages/persistence.py` — élimine les 115 lignes de §2:441-576.
  5. Câbler `price_history_recorder.py` (Phase 0) dans `price_history.py` — collapse les 3 paths inline en un appel par chemin.
  6. Extraire `progress_tracker.py` — la portion la plus délicate car elle touche les commit boundaries. Vérifier en boucle le compteur commits/rollbacks du fixture.
  7. Extraire les `stages/{classification,extraction,persistence}.py` — chaque stage devient indépendamment mockable grâce aux Protocols introduits à l'étape 1.
  8. Collapse les 3 imports paresseux de §2:156, :157, :487 en imports module-level dans `stages/classification.py` et `stages/extraction.py` (l'interface seam les neutralise).

### Total estimated effort

- Phase 0 : **~M-L** (8-12h) — 4 modules partagés + chartests préalables.
- Phase 1 : **~M-L** (7-11h) — §4+§5 couplés, dissolution singleton.
- Phase 2 : **M** (4-6h) — §1, helpers Phase 0 cablés.
- Phase 3 : **M** (4-6h) — §3, fermeture fuite `TwoFactorAuth`.
- Phase 4 : **L** (12-16h) — §2, interface seam A.1 + 600 lignes risquées.

**Total : ~35-51 heures de refactor focalisé** (≈ 1-1.5 semaines de développement plein-temps, à étaler sur 2-3 sprints en pratique pour maintenir la qualité de revue et laisser tourner les tests d'intégration en pré-prod entre phases).

### Caveats

- **Phase 0 doit être 100% complète avant Phase 1.** Une Phase 0 partielle (par ex. modules livrés sans chartests, ou chartests partiels) invalide le filet de sécurité et fige la duplication dans la nouvelle arborescence — annulant le ROI de l'audit. Si l'effort Phase 0 dépasse les estimations, **réduire le scope C1 à Phases 0-2 plutôt que sacrifier la Phase 0**.
- **Phases 1 (§4+§5) ne peuvent pas être splittées.** Per A.4, shipper §4 sans §5 ou inversement laisserait le code dans un état *encore plus* fragmenté (3 templates externalisés + 3 inline + singleton intact) que l'état actuel. Les deux fichiers doivent atterrir dans le même PR ou dans une chaîne de PRs sans interruption.
- **L'interface seam de Phase 4 (A.1) est un investissement architectural à isoler.** Si Phase 4 dépasse 16h, splitter en deux PRs : (4a) interface seam seule, validée par re-routing des imports paresseux vers les Protocols sans déplacer le code ; (4b) découpage en sous-modules. (4a) est shippable indépendamment et améliore la testabilité même si (4b) est différé.
- **Phase 2 et Phase 3 peuvent être shippées en parallèle** si la capacité d'équipe le permet : elles touchent des fichiers indépendants (api/subscriptions.py vs api/auth.py), consomment des modules Phase 0 différents, et n'ont aucune dépendance bidirectionnelle. La séquence linéaire proposée est défensive — favorise la validation incrémentale des helpers Phase 0 sur §1 avant de les engager sur §3.
- **Les ~54 balises HTML dans les 5 tâches Celery périphériques** (`tasks/{budget_alerts,renewal_reminders,trial_reminders,system_announcements,price_change_monitor}.py`) ne sont **pas dans C1**. C'est un travail naturel de continuation après Phase 1 (consolidation `services/email/templates/`), à scoper en C2 avec sa propre roadmap.
- **La double système de préférences "language" de §3** (JSONB `settings` + colonne `preferred_language`) n'est pas tranchée par le découpage : c'est un débat de schéma à mener séparément (cf. §C).

## §C — Out-of-scope

The following items were observed during the C6 audit but are explicitly NOT addressed in C1's roadmap. Each entry explains why it was deferred and names the specific follow-up that should own it.

### C.1 — `docs/architecture/auth.md` doc/code drift + stale reconcile marker

- **Description**: The auth architecture doc lists 5 endpoints; `api/auth.py` exposes 19 (6 2FA endpoints, 6 account-management endpoints, 2 email-verification endpoints, and the base 5). The response shape for `POST /register` also diverges from the documented contract. A pre-existing `<!-- duplicates the above; reconcile manually -->` marker at `auth.md:99` (left from a prior doc-refactor session) compounds the drift.
- **Why deferred**: This is a documentation PR, not a code change — it carries zero production risk and zero dependency on C1's phase ordering. Conflating it with Phase 3 (the `api/auth/` code split) would create an oversized PR with two unrelated concerns.
- **Suggested follow-up**: A standalone "doc reconciliation" PR, ideally opened immediately after Phase 3 ships (the code will be in its final shape then). Candidate sub-project label: **C7-doc-audit**. Scope: regenerate the endpoint table from the router, update the register response schema, and delete the stale marker.

### C.2 — Dual language-preference system in `api/auth.py`

- **Description**: `api/auth.py` lines 562-652 expose two parallel mechanisms for storing user language preference — a dedicated `preferred_language` column and a JSONB `settings` blob — suggesting an incomplete migration that was never resolved. The two tracks are independently readable and writable.
- **Why deferred**: Resolving this requires a schema decision (keep column, deprecate JSONB key, or vice-versa) and a data migration, neither of which can be done mechanically during a code-split refactor. Introducing it into Phase 3 would conflate structural refactoring with schema evolution and balloon the PR scope.
- **Suggested follow-up**: A dedicated cleanup ticket/mini-audit after Phase 3 lands. If the Phase 3 PR reviewer determines the resolution is straightforward (e.g., JSONB key is already unused), it can be absorbed into Phase 3's PR as a trailing commit; otherwise it becomes a separate "language-pref migration" PR with an Alembic migration.

### C.3 — Dead duplicate import `verify_password` at `api/auth.py:672`

- **Description**: `verify_password` is imported from `app.security.password` at the module top (line 35) and re-imported identically at line 672 inside a function body. The second import is dead code and has no effect at runtime.
- **Why deferred**: It is a one-line removal with zero risk, but touching `api/auth.py` before Phase 3 creates a spurious diff that pollutes `git blame`. Phase 3 already targets this exact file for a full split.
- **Suggested follow-up**: Remove in Phase 3, Step 6 (already noted in the Phase 3 concrets list at §A Phase 3.6). No separate ticket needed — it is tracked there.

### C.4 — Peripheral inline HTML in 5 Celery task files

- **Description**: Approximately 54 HTML tags are scattered inline across `tasks/{budget_alerts,renewal_reminders,trial_reminders,system_announcements,price_change_monitor}.py`. These files were not among the audited top-5 god-files but share the same rendering/delivery boundary inconsistency documented in §A.4.
- **Why deferred**: Phase 1 (C1) consolidates the rendering split for the audited god-files (`email_templates.py` + `email_service.py`) and establishes the `services/email/templates/` package pattern. Migrating the Celery task files before that package exists would produce a second intermediate state worse than the current one.
- **Suggested follow-up**: A **C2 sub-project** (or "C1-extension" ticket) opened once Phase 1 ships. Scope: migrate the 5 task files' inline HTML into the `services/email/templates/` package using the pattern established by Phase 1. Estimated size: S-M.

### C.5 — `notification_service.py` as redundant indirection

- **Description**: `notification_service.py` is the sole caller of the three typed wrappers (`send_renewal_reminder`, `send_weekly_summary`, `send_monthly_summary`) in `email_service.py`, while `summary_tasks.py` bypasses those wrappers entirely and calls `email_service.send_email` directly. The file therefore acts as a thin, partially-redundant dispatch layer with no clear contract of its own.
- **Why deferred**: Phase 1 already removes the three typed wrappers from `email_service.py` and migrates their three call-sites in `notification_service.py` to the new `EmailTemplates + transport.send_email` pattern (Phase 1 concret 4). After that migration, whether `notification_service.py` itself should survive as a module or be dissolved is a separate architectural question that requires observing the post-Phase-1 shape.
- **Suggested follow-up**: A mini-audit of `notification_service.py` immediately after Phase 1 ships, before C2 starts. If it reduces to fewer than ~20 lines of glue with no independent logic, dissolve it; otherwise document its contract and keep it. Decision should be recorded in the C2 sub-project spec.

### C.6 — Stale `.pyc` for deleted test (`test_email_service.cpython-311-pytest-7.4.4.pyc`)

- **Description**: `backend/tests/__pycache__/test_email_service.cpython-311-pytest-7.4.4.pyc` exists with no corresponding `.py` source file, indicating the test was deleted without cleaning its bytecode artefact. No `.gitignore` rule currently excludes `__pycache__/` from the `tests/` directory.
- **Why deferred**: Deleting a stale `.pyc` is a one-command cleanup with no code impact, but it belongs in a broader workspace-hygiene pass rather than in an audit PR focused on architecture.
- **Suggested follow-up**: Add `tests/__pycache__/` to `.gitignore` (or verify the root `__pycache__` rule covers it) and delete the stale file in a **hygiene sweep commit** — suitable as a "good first issue" or bundled with the pre-commit hook audit (see C.7).

### C.7 — Graphify false dependency edge (Python → frontend service-worker bundle)

- **Description**: The GRAPH_REPORT contains the edge `_sync_mailbox_async() → isInstance()` resolved to `frontend/dev-dist/workbox-52f2a342.js` — a clearly incorrect cross-language link from a Python async function to a Workbox service-worker bundle in the frontend build artefact directory.
- **Why deferred**: This is a tooling/configuration issue in the graphify analyser, not a code defect. Fixing it requires excluding `frontend/dev-dist/` (and potentially `frontend/dist/`) from the graphify analysis scope, which is outside the C6 audit mandate.
- **Suggested follow-up**: Open a **graphify tooling improvement** ticket: add `frontend/dev-dist/` and `frontend/dist/` to the graphify exclusion list (`.graphifyignore` or equivalent config). Verify by re-running `graphify update .` and confirming the false edge disappears from `graphify-out/GRAPH_REPORT.md`.

### C.8 — Large files outside the top-5 audit scope

- **Description**: Seven backend files exceeded 450 lines but were not audited in C6 because they did not rank in the top-5 by composite god-file score: `api/mailboxes.py` (743 lines), `api/oauth.py` (547), `services/cancellation_research.py` (465), `services/review_suggestions.py` (457), `services/ai_optimizer.py` (455), `tasks/notifications.py` (453), `tasks/price_change_monitor.py` (452). Their architectural health is unknown.
- **Why deferred**: The C6 audit was scoped to the top-5 highest-composite god-files to keep the roadmap actionable. Auditing seven additional files in the same pass would have produced a plan too large to execute in a single sub-project.
- **Suggested follow-up**: A **C6-bis audit pass** once C1 lands, using the same per-file scoring template. `api/mailboxes.py` (743 lines) should be prioritised first given its size. Frontend audit remains blocked on C3 (testing baseline) and is deferred to a **C6-bis-frontend** pass after C3 completes.
