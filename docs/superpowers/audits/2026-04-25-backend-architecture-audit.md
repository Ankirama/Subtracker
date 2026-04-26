# Backend Architecture Audit — 2026-04-25

> Targeted audit of the 5 largest backend Python modules (~5,665 LoC total).
> Driven by the C decomposition (sub-project C6).
>
> **Spec:** `docs/superpowers/specs/2026-04-25-c6-backend-architecture-audit-design.md`
> **Plan:** `docs/superpowers/plans/2026-04-25-c6-backend-architecture-audit.md`

## Method

This audit applies a fixed per-file template (Symptoms / Responsibilities identified / Couplings / Test coverage / Proposed split / Effort & dependencies) to the 5 largest backend Python files, then synthesises three cross-cutting sections:

- **§A — Cross-cutting findings** — duplication patterns, layer violations, circular imports affecting 2+ files.
- **§B — Prioritised roadmap** — recommended execution order with justification.
- **§C — Out-of-scope** — items noted but not addressed in this audit.

Source data: the source files themselves, their associated test files (if any), and `graphify-out/GRAPH_REPORT.md`. T-shirt sizing (S/M/L/XL), not hour estimates.

## §1 — `backend/app/api/subscriptions.py` — 1441 lines

### Symptoms

Single FastAPI router file aggregating **17 endpoints** (one inline helper plus 17 `@router.*` decorators between lines 61 and 1256) covering CRUD, stats, analytics, duplicate detection, merge/split, status reconciliation, feedback capture, price history, and AI cancellation-suggestion workflows. The file mixes thin CRUD handlers (e.g. `delete_subscription`, lines 736-763) with heavy in-handler business logic — `get_analytics_trends` alone spans **162 lines** (272-433) and reimplements monthly cost projection from scratch with nested loops, `defaultdict`, and `relativedelta` arithmetic. Two **lazy intra-function imports** betray the layering issue: line 783 imports from `app.tasks.email_sync` and line 1045 imports from `app.services.renewal_calculator`, indicating the module reaches into both the Celery layer and an additional service to avoid module-level circulars. Section structure is implicit: there are no `# === chapter ===` markers, only a lone `# Price History Endpoints` divider at line 964, so concerns are interleaved by historical accretion rather than by design. Cost-projection logic (`amount * 12`, `amount / 12`, `amount * 4.33`, `amount / 3`, `amount / 6`) is **duplicated three times** — at 207-217, 229-236, and 327-338 — confirming the absence of a shared helper. The file imports six SQLAlchemy models directly (User, Mailbox, Subscription, subscription_emails, SubscriptionFeedback, PriceHistory) and mutates the `subscription_emails` association table by raw SQL in two distinct endpoints (merge at 595-599, split at 1406-1411), so the API layer also acts as a partial repository.

### Responsibilities identified

1. **CRUD subscription** (lines 61-107, 632-733, 736-763) — `create_subscription`, `get_subscription`, `update_subscription`, `delete_subscription`. Standard resource lifecycle.
2. **List & filter** (lines 109-169) — `list_subscriptions` with mailbox/status/category/trial filtering and pagination.
3. **Aggregated stats** (lines 172-268) — `get_subscription_stats`: monthly/yearly cost rollup, by-category, by-cycle, upcoming renewals.
4. **Historical analytics** (lines 271-433) — `get_analytics_trends`: 162-line monthly time-series engine with inline cost projection, category trends, peak detection.
5. **Duplicate detection / resolution** (lines 436-507, 510-629) — `find_duplicate_subscriptions` (heuristic grouping + similarity scoring) and `merge_subscriptions` (transactional merge with price-history side-effects and raw `subscription_emails` SQL).
6. **Status reconciliation** (lines 766-839, 1030-1134) — `update_subscription_status` (delegates to `app.tasks.email_sync.update_subscription_statuses` via lazy import) and `update_subscription_renewal_status` (re-runs `RenewalCalculator` over all user subs from inside the request handler — 100+ lines of orchestration).
7. **Feedback collection (ML training data)** (lines 842-961) — `create_subscription_feedback`: builds a JSON snapshot of the subscription before deletion for AI feedback loops.
8. **Price history (pass-through)** (lines 967-1027) — `get_subscription_price_history`, `get_subscription_price_statistics`: thin wrappers over `PriceHistoryService`.
9. **Cancellation suggestion workflow** (lines 1137-1253) — `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion`: AI suggestion lifecycle (apply / clear).
10. **Manual split** (lines 1256-1441) — `split_subscription`: 185-line endpoint that re-creates subscriptions and rewires the `subscription_emails` association table by raw SQL.

### Couplings (graph-derived)

- **Inbound imports**: 1 module imports the router — `backend/app/main.py:133` only (re-exports as `/api/subscriptions`). No service or task imports symbols from this file, which is healthy: the router is a leaf in the import DAG.
- **Outbound imports**: 14 modules. Notable / surprising:
  - `app.models.email_message.subscription_emails` (association table) — used to perform raw `db.execute(subscription_emails.update()...)` mutations directly from the API layer (merge line 595, split line 1406). This bypasses both `Subscription` and any repository abstraction.
  - **Cross-layer lazy imports** (in-function): `from app.tasks.email_sync import update_subscription_statuses` (line 783) and `from app.services.renewal_calculator import RenewalCalculator, get_subscription_emails` (line 1045). Their placement inside handlers is a deliberate workaround — likely for circular-import avoidance — and signals that these endpoints conceptually belong to those layers, not to the API.
  - 6 model imports + 2 schema modules + 1 service (`PriceHistoryService`) + auth deps. No frontend / no infra.
- **Centrality**: `api/subscriptions.py` itself is **not named** as a god node in `GRAPH_REPORT.md`, but its central domain entity `Subscription` is flagged at **0.145 betweenness centrality** (line 1266) bridging Communities 0/1/2/3/4/6/8/9/11/12/13/15/16/17, and `Subscription` carries **816 inferred edges** (line 1272). The file is the principal HTTP surface for that high-centrality entity, which explains its size.

### Test coverage

- Test file: `backend/tests/test_subscriptions_api.py` (899 lines, **40 `def test_` functions**).
- Approximate coverage estimate: **~65% of routes** have at least one happy-path + auth test. Tests cover: list (5 cases), get-by-id (3), create (3), update (3), delete (3), stats (3), update-status (2), analytics-trends (5), feedback (4), price-history (4), price-statistics (4). **Routes with zero tests**: `find_duplicate_subscriptions`, `merge_subscriptions`, `update_subscription_renewal_status`, `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion`, `split_subscription`. Notably the six untested routes are the **most complex and most mutation-heavy** in the file (transactional merges, raw association-table SQL, multi-subscription rewrites).
- Refactor safety: **risky**.
- Justification: the simple CRUD/list/stats/analytics surface (≈ 60% of LoC) is well-tested and can be extracted safely; but the ~480 lines of merge / split / renewal-reconciliation / cancellation-suggestion logic has **no test scaffold**, and the merge and split paths perform raw SQL mutations on `subscription_emails` that would be silently broken by an extraction error. Any decomposition of those endpoints **must be preceded by characterisation tests**.

### Proposed split

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

### Effort & dependencies

- **Effort**: **M**.
- **Effort justification**: ~60% of LoC is mechanical move-and-import; ~40% (merge, split, renewal reconciliation, cancellation-suggestion) requires writing characterisation tests **before** moving, plus extracting the cost-projection helper. Estimated 4-6h: 1h scaffold the sub-package, 2h move tested endpoints + run `test_subscriptions_api.py`, 2h write characterisation tests for the 6 untested routes, 1h move them. No public API URL changes (router prefix `/api/subscriptions` stays in `main.py`).
- **Blockers**: _None._ The file is a leaf in the import DAG; only `main.py` imports it. No upstream refactor required.
- **Blocks**: §A cross-cutting work on cost-projection duplication (the same arithmetic appears in `tasks/email_sync.py` and likely in `services/`). Splitting this file first lets §A target a single shared helper rather than chasing inline copies.
- **Risk**: **medium**.
- **Risk justification**: HTTP contracts are stable (only `main.py` consumes the router; frontend uses the URL paths, not Python imports), but the merge and split paths mutate the `subscription_emails` association table via raw SQL with **zero test coverage** — an accidental import-path or transaction-scope change would corrupt data silently. Mitigation: write `test_merge_subscriptions.py` and `test_split_subscription.py` characterisation tests **before** moving those handlers; treat them as a quality gate.

## §2 — `backend/app/tasks/email_sync.py` — 1410 lines

### Symptoms

A single Celery task module that bundles **2 task entry points** (`sync_mailbox_emails` line 938, `check_scheduled_syncs` line 1320) plus **3 module-level helpers** (`filter_subscription_data` line 63, `update_subscription_statuses` line 1198, `parse_date_filter` line 1282), but the bulk of the file is a single **820-line god function**: `_sync_mailbox_async` runs from line 88 to line 922 and orchestrates every stage of the pipeline inline — credential decryption, provider instantiation, date-filter resolution, paginated fetch, classification, extraction, deduplication / service-reference matching, subscription upsert, price-history bookkeeping, renewal calculation, cancellation-suggestion creation, association-table writes, progress persistence, cancellation polling, and history-entry updates. Three **lazy intra-function imports** (line 156 `app.services.ai_classifier`, line 157 `app.services.subscription_extractor`, line 487 `app.services.reference_extractor`) confirm circular-import pressure between this task module and the AI services layer. A nested `try/except` block 5 levels deep (lines 334-808) wraps the per-email processing, and the duplicate-resolution heuristic (service references → email_sender match → custom_label keywords → fallback to first match, lines 462-576) is **115 lines of inline policy** with magic-keyword lists (`"tier"`, `"channel"`, `"plan"`, …) and a hard-coded payment-processor list (`"paypal"`, `"stripe"`, `"paddle"`, `"gumroad"`, `"fastspring"`, line 451) embedded in the orchestrator. Price-change arithmetic (`(new - old) / old * 100`, classified into `"increase"`/`"decrease"`) is **duplicated twice** at lines 374-394 (AI-flagged price update) and 602-625 (post-hoc detection on update). The orchestrator persists progress (`mailbox.last_sync_*`, `current_batch_number`, `progress_percentage`, `estimated_completion_time`, history-entry fields) inline at three different commit points in the same loop body, and the `sync_mailbox_emails` Celery task itself reimplements **80+ lines of completion / failure / auth-error bookkeeping** (lines 1045-1195) that mirrors the in-loop bookkeeping.

### Responsibilities identified

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

### Couplings (graph-derived)

- **Inbound imports**: 3 modules import from this file.
  - `backend/app/api/mailboxes.py:355, :474` — both lazy intra-function imports of `sync_mailbox_emails` (suggesting `mailboxes.py` is also fighting circulars; same anti-pattern as `api/subscriptions.py`).
  - `backend/app/api/subscriptions.py:783` — lazy intra-function import of `update_subscription_statuses` (already documented in §1).
  - `backend/tests/test_email_sync.py:11` — module-level import for tests.
  - The fact that **every production caller uses lazy imports** is itself the diagnostic finding: this module is a circular-import hub for the API layer.
- **Outbound imports**: this file imports from **17 distinct modules**, of which 3 are intra-function (lazy):
  - Module-level (14): `celery`, `sqlalchemy.orm`, `app.celery_app`, `app.database`, 5 model modules (`mailbox`, `subscription`, `email_message`, `price_history`, `sync_history`), 2 provider modules (`app.email_providers`, `app.email_providers.gmail`), `app.security.encryption`, `app.config`, `app.utils.config_helper`, `app.services.renewal_calculator`, `app.services.email_filter`.
  - **Lazy / cross-layer** (3): `app.services.ai_classifier` (line 156), `app.services.subscription_extractor` (line 157), `app.services.reference_extractor` (line 487). These three services almost certainly consume something this module also exports (likely shared types or DB models), making the circular hard to break without an interface seam.
- **Centrality**: `email_sync.py` itself is **not named** as a god node in `GRAPH_REPORT.md`, but it appears in the "Surprising Connections" section at line 228-229: `_sync_mailbox_async()` is flagged with an inferred call to `isInstance()` in a frontend workbox bundle — a graph-extraction artefact, but the listing confirms `_sync_mailbox_async` is a high-fan-out node. The downstream entities `Subscription`, `Mailbox`, `EmailMessage`, `PriceHistory` are all in the GRAPH_REPORT top-10 inferred-edge list (816 / 305 / 136 / 148 edges respectively, lines 217-225 of GRAPH_REPORT) and **all four are written by this single function**.

### Test coverage

- Test file: `backend/tests/test_email_sync.py` (518 lines, **22 `def test_` functions**, 3 test classes: `TestParseDateFilter` 9 tests, `TestUpdateSubscriptionStatuses` 5 tests, `TestSyncMailboxEmails` 8 tests).
- Approximate coverage estimate: **~30-40% of LoC**. The two small helpers are well-covered: `parse_date_filter` has 9 happy-path + edge-case tests (singular/plural, whitespace, case, default fallback), and `update_subscription_statuses` has 5 tests (activation, deactivation, manual-override, weekly cycle, yearly cycle). The Celery task itself has 8 tests but they are **outer-shell tests**: nonexistent mailbox, inactive mailbox, exception path, resume from cancelled, force-full-sync, custom date filter, progress-tracking clearance, and one "successful sync" test. Inspection of those tests (lines 267-518) shows they mock `_sync_mailbox_async` or its dependencies — the **inner pipeline (classification → extraction → dedup heuristic → price-history → renewal → cancellation suggestion → association-table writes) has zero behavioural coverage**. Specifically untested: service-reference matching (lines 485-509), payment-processor branch (lines 451-460, 527-533), email_sender / custom_label disambiguation (lines 535-576), AI-flagged price-update path (lines 345-440), post-hoc price-change detection (lines 580-630), renewal-calculator integration (lines 664-731), cancellation-suggestion creation (lines 733-767), and the cancellation-polling + history-entry update on cancel (lines 863-899).
- Refactor safety: **risky**.
- Justification: outer Celery-task contract (input UUID, retry policy, status fields, return shape) is well-tested and would survive an extraction unchanged; but ~600 of the 820 lines inside `_sync_mailbox_async` represent **untested business policy** (multi-strategy dedup, three price-history paths, cancellation suggestion, renewal recalculation, progress persistence). Any extraction that re-orders, re-commits, or re-rolls-back differently could silently change which emails get classified, which subscriptions get merged versus duplicated, or whether progress survives interruption — and there is no characterisation harness to catch it.

### Proposed split

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

### Effort & dependencies

- **Effort**: **L**.
- **Effort justification**: ~30% of LoC has tests and is a mechanical move (the two helpers, the Celery task shell, `parse_date_filter`); ~70% — the 600 untested lines of `_sync_mailbox_async` business logic — requires writing **characterisation tests before extracting**, especially for the multi-strategy dedup, the three price-history paths, and the cancellation suggestion flow. Roughly: 2h scaffold the sub-package and move the tested helpers (`parse_date_filter`, `update_subscription_statuses`, `DatabaseTask`, `filter_subscription_data`); 4h write characterisation tests for dedup strategy, price-history paths, renewal step, cancellation step (using factory/fixture builders for `EmailMessage`+`Subscription` graphs); 4h extract `dedup_strategy.py` + `price_history.py` + `renewal_step.py` + `cancellation_step.py` and rewire the orchestrator; 2h extract `progress_tracker.py` and the stage modules; 2h-4h iterate on the inevitable hidden coupling (commit boundaries, lazy-vs-eager flush, association-table relationship checks). Realistic 12-16h.
- **Blockers**: _None._ The 3 inbound callers (`api/mailboxes.py`, `api/subscriptions.py`, `test_email_sync.py`) all import named symbols that can be re-exported from `__init__.py` for compatibility.
- **Blocks**: §A cross-cutting work on (a) cost-projection / price-change arithmetic duplication shared with `api/subscriptions.py`, (b) circular-import hygiene between the API layer and AI services (`api/subscriptions.py` lazy import of `email_sync`, `email_sync` lazy imports of three AI services). Splitting this file lets §A target a single shared helper module (`app/services/price_history_recorder.py`) instead of chasing inline copies, and the new `dedup_strategy.py` becomes the canonical home for dedup policy that `api/subscriptions.find_duplicate_subscriptions` (currently 71 lines of inline scoring at §1 lines 436-507) could also delegate to.
- **Risk**: **high**.
- **Risk justification**: this code is **on the data-write path for every subscription, every email, every price-history entry, and every association-table row** — the four highest-edge entities in the graph (`Subscription` 816, `Mailbox` 305, `PriceHistory` 148, `EmailMessage` 136). The 5-level-deep `try/except` + per-email `db.commit()` + `db.rollback()` (line 803, 807) means transaction granularity is implicit and **any extraction that accidentally hoists a commit out of the per-email scope will batch-corrupt rollback semantics**. The cancellation polling reads `mailbox.sync_cancellation_requested` after `db.refresh(mailbox)` (line 864) — moving that out of the orchestrator without preserving the refresh-then-read ordering will silently break user-initiated cancellations. Mitigation: **mandatory characterisation tests before any extraction**; use a transaction-checkpoint test fixture that records `db.commit()` / `db.rollback()` call counts and verifies they are unchanged after refactor; treat the 600 untested lines as a quality gate identical to the merge/split paths flagged in §1.



## §3 — `backend/app/api/auth.py` — 1191 lines

### Symptoms

Single FastAPI router file aggregating **19 endpoints** spanning seven distinct auth flows (registration with invite-token gating, login with brute-force tracking, refresh, logout, account management, two-factor authentication, and email verification) with only two implicit `# section` comments (`# Account Management Endpoints` line 484, `# Two-Factor Authentication Endpoints` line 695, `# Email Verification Endpoints` line 1031) marking the boundaries. The handlers carry heavy in-line policy: `register` (lines 64-203, **140 lines**) interleaves invite-token validation, duplicate-email detection, password hashing, user-row creation, invite-token consumption, frontend-URL composition, and email dispatch — the lone composite of business and side-effect logic for a single HTTP path. `login` (lines 206-355, **150 lines**) hard-codes the brute-force threshold (`failed_attempts >= 5` line 231), branches on 2FA method (`email`/`totp`), sends OTP emails inline, and creates JWTs — all in one function. **Two lazy intra-function imports** confirm circular-import pressure: `from app.models.invite_token import InviteToken` at line 86 (inside `register`) and `from app.security.password import verify_password` at line 672 (inside `delete_account`, redundant with the module-level import at line 35). The 2FA flow alone aggregates **6 endpoints** (`verify-login`, `setup`, `enable`, `disable`, `status`, `backup-codes/regenerate`) totalling ~330 lines (698-1028) that all share the same `if user.two_factor_enabled` / `else` branching pattern but never reify it into a guard. The "send verification email and bail with 500 if it fails" pattern is **duplicated three times** (lines 191-198 register, lines 316-321 login OTP send, lines 829-836 2FA email setup, lines 1180-1185 resend-verification), each rebuilding the `EmailService(db)` instance and the `(success, error)` tuple-handling. The `frontend_url + verification_url` construction is **duplicated twice** (lines 179-180 register, lines 1170-1171 resend-verification), and the `display_name = user_data.display_name or user_data.email.split("@")[0]` fallback appears in three forms (lines 184, 312, 825, 1175). Finally, the docstring for `register` still claims "If verification fails" (line 84) while the code actually returns 500 with a "try resending" message — minor doc/code drift inside the file itself.

### Responsibilities identified

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

### Couplings (graph-derived)

- **Inbound imports**: 1 module imports the router — `backend/app/main.py:131` only (`auth.router` mounted at `/api/auth` via line 158). No service or task imports symbols from this file. Healthy import-DAG leaf, mirroring §1.
- **Outbound imports**: 16 module-level imports + 2 lazy intra-function imports.
  - Module-level (16): `fastapi`, `sqlalchemy.orm`, `jose`, `app.database`, `app.models.user`, `app.schemas.auth` (22 schema names), `app.security.password`, `app.security.jwt`, `app.security.dependencies`, `app.security.events` (3 names), `app.security.two_factor` (4 names), `app.services.email_service`, `app.security.email_verification` (2 names), `app.config`, `app.utils.config_helper`, `datetime`, `logging`. The fan-out into `app.security.*` (5 distinct sub-modules) is itself a smell: this router is the **only** consumer of most of those packages, and the abstraction boundary leaks (e.g. `TOTPManager`, `EmailOTPManager`, `BackupCodesManager` all imported at the API layer rather than hidden behind `TwoFactorAuth`).
  - **Lazy / cross-layer (2)**: `from app.models.invite_token import InviteToken` line 86 (inside `register`, almost certainly because import-time would create a circular through `User.invites` relationship), `from app.security.password import verify_password` line 672 (inside `delete_account`, **redundant** with the module-level import at line 35 — dead duplication, not a circular workaround). Only one of the two is a genuine architecture signal.
- **Centrality**: not flagged as a god node in `GRAPH_REPORT.md` ("God Nodes" top-10 lines 215-225 lists no API module). The file appears once in "Surprising Connections" (line 230-231): `update_preferences()` → `isInstance()` in a frontend workbox bundle — a graph-extraction artefact, but indicating `update_preferences` itself was indexed as a notable node. The downstream `User` entity is the **#1 god node with 1019 edges** (line 216), and this file is the principal HTTP surface that mutates `User.password_hash`, `User.email_verified`, `User.two_factor_enabled`, `User.backup_codes`, `User.settings`, `User.preferred_language`, `User.email_verification_token` — i.e. the file is the primary write path into the most-connected entity in the graph. Community 18 (line 315) groups `get_current_active_user`, `get_current_admin_user`, `get_current_user`, "FastAPI dependencies for authentication" and 39 other auth-related nodes — this file is one of two main consumers.

### Test coverage

- Test file(s) found: `backend/tests/test_auth.py` (533 lines, **35 `def test_` functions**, 7 test classes).
- Approximate coverage estimate: **~25-30% of routes** have at least one happy-path + auth test. Tested routes: `register` (4 cases — success with mocked email, duplicate, invalid email, weak password), `login` (4 — success, wrong pwd, nonexistent, inactive), `refresh` (5 — success, access-token-as-refresh, invalid, expired, inactive), `me` (3), `logout` (2). The remaining 17 tests target `app.security.*` units (encryption 5, JWT 5, dependencies 6) — not endpoints. **14 of the 19 routes have zero endpoint tests**: `update_profile`, `change_password`, `update_preferences`, `get_language_preference`, `update_language_preference`, `delete_account`, **all 7 2FA endpoints** (`verify-login`, `setup`, `enable`, `disable`, `status`, `backup-codes/regenerate`), `verify_email`, `resend_verification`. The 2FA email-OTP path, the auto-login on email verification, and the brute-force IP-block flow are **completely untested**.
- Refactor safety: **risky**.
- Justification: the small core (register, login, refresh, me, logout — ~430 LoC, ~36% of file) is well-tested and would survive an extraction unchanged; but the ~760 LoC of account management, 2FA, and email verification logic — including security-critical paths (backup-code generation, TOTP secret handling, password change, account deletion, brute-force IP-block) — has no characterisation harness. Any decomposition error in the 2FA flow or the email-verification auto-login path would silently weaken authentication guarantees.

### Proposed split

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

### Effort & dependencies

- **Effort**: **M**.
- **Effort justification**: ~36% of LoC (register, login, refresh, me, logout) has tests and is a mechanical move; ~64% (account management, 2FA, email verification) requires writing endpoint-level characterisation tests **before** moving, particularly for the 2FA enable/disable/regenerate flow and the email-verification auto-login. Estimated 4-6h: 1h scaffold the sub-package + extract `_email_dispatch.py`, 1h move `login` + `registration` (tested), 2h write characterisation tests for the 7 untested 2FA endpoints + verify-email auto-login + delete-account + change-password + brute-force flow, 2h move `account.py` and `two_factor.py`. No public API URL changes (router prefix `/api/auth` stays in `main.py:158`); the FastAPI `tags=["Authentication"]` annotation may want subdivision (`Authentication`, `2FA`, `Account`, `Email Verification`) which is a separate cosmetic PR.
- **Blockers**: _None._ The file is a leaf in the import DAG; only `main.py` imports it. The lazy `InviteToken` import is a relationship-cycle, not an architecture-cycle, so it does not need to be untangled to ship the split.
- **Blocks**: §A cross-cutting work on (a) the duplicated `EmailService.send_*` / `(success, error)` pattern (also appears in `services/email_service.py` consumers, see §5), (b) the doc/code drift versus `docs/architecture/auth.md`. Splitting this file first lets §A reference a stable target structure when documenting the email-dispatch helper, and the new sub-package becomes the canonical surface to update in `docs/architecture/auth.md` (which today documents only 5 of the 19 endpoints — see §C).
- **Risk**: **medium**.
- **Risk justification**: HTTP contracts are stable and only `main.py` consumes the router; the frontend uses URL paths, not Python imports. However, the 2FA enable / verify-login / regenerate-backup-codes paths mutate `User.two_factor_enabled`, `User.backup_codes`, and `User.totp_secret` with **zero endpoint coverage** — an accidental import-path change or a misplaced commit boundary in the 2FA setup flow could silently weaken backup-code regeneration (e.g. issuing the new codes but failing to persist them, or persisting plaintext instead of hashed). Mitigation: write `test_2fa_endpoints.py` and `test_email_verification_endpoints.py` characterisation tests **before** moving those handlers, and add a security-event-log assertion to confirm side-effect parity.

## §4 — `backend/app/services/email_templates.py` — 841 lines

### Symptoms

Contrary to what the name suggests, this file is **not** a registry of inbound email parsers per provider (Netflix, Spotify, etc.) — it is an outbound HTML template generator (subscription summary, 2FA OTP, email verification). The three public methods each produce a complete HTML document via multi-line f-strings: `generate_summary_email` (lines 14-266, ~252 lines), `generate_2fa_otp_email` (lines 481-658, ~178 lines), `generate_email_verification_email` (lines 661-841, ~181 lines). Each method embeds its own duplicated CSS stylesheet (body, container, gradient header `#667eea → #764ba2`, SubTracker footer, mobile media query at 600px) — about 60 near-identical CSS lines repeated three times (lines 38-194, 502-611, 680-787). The `summary_email` additionally aggregates 7 private `_render_*` helpers (lines 269-478) which produce HTML fragments per section (insights, changes, categories, top subs, AI insights/recos, renewals) with their own inline style. The result is a stateless 841-line static class, ~85% literal HTML/CSS and ~15% rendering logic, where any branding change (logo, palette, footer) requires a triple manual edit.

### Responsibilities identified

1. **"Subscription summary" template (orchestrator)** (lines 14-266) — assembles user statistics, insights, AI recommendations, changes, categories, top subs, and renewals into a single HTML email with a CTA toward `/subscriptions`.
2. **Summary fragment rendering helpers** (lines 269-478) — 7 `_render_*` functions (insights, changes, top_categories, top_subscriptions, ai_insights, ai_recommendations, upcoming_renewals) each returning an HTML string or `""` if data is empty; `_render_upcoming_renewals` imports `datetime` locally (line 463) instead of using the top-level import.
3. **"2FA OTP" template** (lines 481-658) — transactional email for a 6-digit verification code with expiration, security warnings, "info-box" and "security-notice" callouts.
4. **"Registration email verification" template** (lines 661-841) — onboarding email with a CTA button `verification_url` (24h expiration), text fallback link, welcome message.
5. **Shared duplicated stylesheet** (lines 38-194, 502-611, 680-787) — SubTracker branding (gradient header, footer, 600px container, font stack `-apple-system,...`, purple palette `#667eea`/`#764ba2`) repeated three times without DRY extraction.

### Couplings (graph-derived)

- **Inbound imports**: Only 3 consumer sites — `app/services/email_service.py:15` (which calls `generate_2fa_otp_email` and `generate_email_verification_email`), and `app/tasks/summary_tasks.py:20` (which calls `generate_summary_email` at 2 locations, lines 90 and 198). Restricted API surface → limited-risk refactor.
- **Outbound imports**: only `from typing import Dict, Any` at the top-level + a local `from datetime import datetime` inside `_render_upcoming_renewals` (line 463). No cross-layer coupling (no SQLAlchemy, no FastAPI, no business models) — pure presentation file.
- **Centrality**: _Not flagged in GRAPH_REPORT._ The report does not mention `email_templates` (`grep` returns 0 occurrences across 4143 nodes), consistent with its role as a pure leaf consumed by 2 modules.

### Test coverage

- Test file(s) found: `backend/tests/test_email_templates.py` (561 lines)
- Approximate coverage estimate: **high (~85-95%)** — 4 test classes (`TestGenerateSummaryEmail`, `TestGenerate2FAOTPEmail`, `TestGenerateEmailVerificationEmail`, `TestRenderHelpers`) with 28 cases covering each public method, each private `_render_*` helper, empty paths, priority/pluralisation variants, top-5 + remainder, and the increase/decrease paths of `net_change`.
- Refactor safety: **safe**
- Justification: assertions test for the presence of text fragments (`"Hi {user_name}!"`, `"€49.95"`, `"💡 Key Insights"`) rather than the exact HTML structure; a sub-module split preserving method names and their exact output will invalidate no assertion, and the suite will run near-instantly (no I/O).

### Proposed split

```
backend/app/services/email_templates/
├── __init__.py              (~15 lines — re-exports `EmailTemplates` for caller backward compatibility)
├── _styles.py               (~80 lines — shared CSS constants: BASE_CSS, HEADER_GRADIENT, FOOTER_HTML, render_layout())
├── summary.py               (~280 lines — generate_summary_email + _render_* helpers, or split between summary.py and summary_sections.py)
├── otp_2fa.py               (~180 lines — generate_2fa_otp_email)
└── verification.py          (~180 lines — generate_email_verification_email)
```

The file's asymmetry (one large orchestrated template + two standalone templates) makes splitting by use-case the most natural approach: each sub-module becomes independently testable and editable. The `_styles.py` module factors out the ~60 CSS lines duplicated three times (header gradient, container, footer, font stack, 600px media query) and provides a `render_layout(title, body_html, frontend_url)` helper that eliminates ~150 lines of boilerplate. To preserve backward compatibility with the two existing callers (`email_service.py`, `summary_tasks.py`), `__init__.py` re-exports an `EmailTemplates` class whose staticmethods delegate to the sub-modules — no caller modification required. Target total ~735 lines (vs current 841) through CSS deduplication.

### Effort & dependencies

- **Effort**: M
- **Effort justification**: mechanical split into 4 sub-modules + shared CSS extraction + backward-compat facade; ~3-5h including 1h to validate that the existing test suite (28 cases) passes without modification, plus a visual review of the rendered emails (Resend offers a preview mode).
- **Blockers**: _None._
- **Blocks**: §5 (`services/email_service.py`) consumes two of the three templates — a hypothetical method rename would directly impact audit §5; keeping the `generate_*` names exposed via `__init__.py` neutralises this coupling.
- **Risk**: low
- **Risk justification**: stateless file, no I/O, no ORM/HTTP dependency; narrow API surface (3 public methods, 2 consumers); high test coverage, behaviour-oriented; visual regressions detectable by automated HTML diff on fixtures.

> **Note for §5 and §A**: `email_service.py` (782 lines, next audit) **delegates** HTML generation to `email_templates.py` — no duplication, the overlap is a healthy dependency (a Resend "delivery" layer + a "rendering" layer). However, the asymmetry is suspicious: `email_service.py` likely also sends other email types (price change, renewal reminder, trial reminder, budget alert, system announcement — to confirm in §5) which could generate their HTML inline rather than via `EmailTemplates`. If so, §A should flag an **extraction inconsistency**: only 3 templates are externalised here; others remain inline in `email_service.py`. Cross-cutting pattern already observed in §3 (`auth.py` also contains email-dispatch helpers — see §3 line 233).

## §5 — `backend/app/services/email_service.py` — 782 lines

### Symptoms

This module is advertised as a "Resend delivery service" (docstring l.2) but ~63% of its volume (lines 287-778, i.e. ~490 of 782 lines) is actually literal HTML/CSS in three inline templates (`_get_renewal_reminder_template`, `_get_weekly_summary_template`, `_get_monthly_summary_template`). So the module mixes three roles: Resend transport configuration, use-case-typed methods (6 `send_*` wrappers), and inline HTML rendering for 3 of them. The cohabitation is **inconsistent**: `send_2fa_otp_email` (l.221) and `send_email_verification` (l.261) delegate cleanly to `EmailTemplates.generate_*`, while `send_renewal_reminder`, `send_weekly_summary` and `send_monthly_summary` keep their HTML in the service. Worse, call-site inspection reveals that **the typed wrappers `send_renewal_reminder` / `send_weekly_summary` / `send_monthly_summary` are nearly dead code in production**: `summary_tasks.py:90,95,198,203` renders itself via `EmailTemplates.generate_summary_email()` then calls `email_service.send_email()` (raw transport); only `notification_service.py:118,136,145` uses the typed wrappers. A singleton instance `email_service = EmailService()` (l.782) is created at module load, which prevents any access to a `db: Session` at init time and partially neutralises the value of the constructor's `db` parameter.

### Responsibilities identified

1. **Resend transport configuration** (lines 23-42) — reads API key and `from` headers via `get_config_value`, global `resend.api_key` configuration.
2. **Generic send** (lines 44-86) — `send_email(to, subject, html, plain)` returning `(success, error)`, logging and exception capture.
3. **Use-case-typed wrappers** (lines 88-285) — 5 methods `send_renewal_reminder`, `send_weekly_summary`, `send_monthly_summary`, `send_2fa_otp_email`, `send_email_verification` that compose subject + plain text + call to the templater + delegation to `send_email`.
4. **Inline HTML rendering for 3 emails** (lines 287-778) — `_get_renewal_reminder_template`, `_get_weekly_summary_template`, `_get_monthly_summary_template`: ~490 lines of HTML/CSS f-string with gradients, layouts, and embedded sorting/filtering logic (`sorted(...)[:10]`, `subscriptions[:5]`, `diff_percent` computation).
5. **Module-level singleton** (line 782) — `email_service = EmailService()` instantiated at import, with no `db` provided, so `get_config_value` always falls back to environment variables.

### Couplings (graph-derived)

- **Inbound imports**: 8 importers identified (`grep -rln 'from app.services.email_service'`):
  - `app/tasks/budget_alerts.py`, `app/tasks/renewal_reminders.py`, `app/tasks/trial_reminders.py`, `app/tasks/summary_tasks.py`, `app/tasks/system_announcements.py`, `app/tasks/price_change_monitor.py` (all via raw `email_service.send_email(...)`)
  - `app/api/auth.py` (via `send_2fa_otp_email`, `send_email_verification` at lines 185, 310, 823, 1176)
  - `app/services/notification_service.py` (only caller of the wrappers `send_renewal_reminder` / `send_weekly_summary` / `send_monthly_summary`)
- **Outbound imports**: `resend`, `sqlalchemy.orm.Session`, `app.config.settings`, `app.utils.config_helper.get_config_value`, `app.services.email_templates.EmailTemplates`. No cross-layer leakage (no import of `app.models.*` or `app.api.*`). **Relationship with `email_templates.py` (§4)**: `EmailTemplates` is imported but used only by 2 of 5 methods — the inverse is also true on the `email_templates.py` side (`generate_summary_email` is never called by `email_service` but directly by `summary_tasks.py`). Responsibility boundary is **blurry and inconsistent** between the two modules.
- **Centrality**: _Not flagged in GRAPH_REPORT.md_ (grep returns no occurrence of the file in the graphify report), but the fan-in of 8 importers and its notification-hub position suggest a de-facto god-node for the notifications layer.

### Test coverage

- Test file(s) found: no direct `test_email_service.py` in `backend/tests/` (a stale `test_email_service.cpython-311-pytest-7.4.4.pyc` lingers in `__pycache__/` → source file deleted without cleaning the cache). Indirect coverage via: `test_renewal_reminders.py`, `test_summary_tasks.py`, `test_trial_reminders.py`, `test_budget_alerts.py`, `test_system_announcements.py`, `test_price_change_monitor.py`, `test_email_verification.py`, `test_email_templates.py`.
- Approximate coverage estimate: ~30-40% — the `send_email` transport and the `send_2fa_otp_email`/`send_email_verification` delegations are likely mocked in upstream tests, but the 3 inline HTML templates and the typed wrappers (`send_renewal_reminder`, `send_weekly_summary`, `send_monthly_summary`) have no direct rendering assertion.
- Refactor safety: **risky**.
- Justification: the absence of a direct test + fan-in of 8 importers + the module-level singleton mean any extraction of the inline templates is detectable only at runtime; a non-regression test on the rendered HTML (snapshot) is a mandatory prerequisite.

### Proposed split

```
backend/app/services/
├── email/
│   ├── __init__.py
│   ├── transport.py              # EmailService (Resend wrapper, send_email only)
│   └── templates/                # restructuring of §4 + inline extraction
│       ├── __init__.py
│       ├── base.py               # shared layout/CSS (deduplication extraction)
│       ├── otp_2fa.py            # already in email_templates.py (§4)
│       ├── verification.py       # already in email_templates.py (§4)
│       ├── summary.py            # already in email_templates.py (§4)
│       ├── renewal_reminder.py   # extracted from email_service.py l.287-424
│       ├── weekly_summary.py     # extracted from email_service.py l.426-596
│       └── monthly_summary.py    # extracted from email_service.py l.598-778
```

This split **merges** the "rendering" role into an extended `email_templates/` package (cf. §4 proposal) and reduces `email_service.py` to a pure transport (~80 lines: `send_email` + config). The 5 typed `send_*_reminder/summary` wrappers are to be **removed**: `notification_service.py` (the only caller) must be migrated to the pattern already used by `summary_tasks.py` (render via `EmailTemplates.*` then `transport.send_email`). Justification: today HTML rendering is duplicated across `email_service.py` (3 templates), `email_templates.py` (3 templates), and **5 `tasks/*` files which each contain 7 to 11 HTML tag occurrences** (`grep` confirms: 8/11/8/11/7 for renewal/trial/system/price/budget) — unification under `services/email/templates/` is therefore a cross-cutting gain, not just local to this file.

### Effort & dependencies

- **Effort**: M
- **Effort justification**: 3 templates to extract (~490 lines of purely movable HTML), 5 typed wrappers to remove + 3 call-sites in `notification_service.py` to migrate, restructuring consistent with §4 (effort partially shared). No business logic to rewrite. Estimated 4-6h including upfront snapshot tests.
- **Blockers**: §4 refactor (`email_templates.py`) to perform simultaneously or upstream to avoid a fragmented intermediate state.
- **Blocks**: extraction of inline HTML present in `tasks/budget_alerts.py`, `tasks/renewal_reminders.py`, `tasks/trial_reminders.py`, `tasks/system_announcements.py`, `tasks/price_change_monitor.py` (5 files, to be addressed in §A after templates-package consolidation).
- **Risk**: medium
- **Risk justification**: no direct test of the module + module-level singleton + 8 importers; mitigation = snapshot tests on the 3 HTML templates before extraction and mocked integration tests on `send_email` to preserve the `(bool, Optional[str])` signature.

## §A — Cross-cutting findings

This section synthesises the patterns observed across §1-§5 that touch at least two of the five audited files. Six findings emerge. Each names a **structural bottleneck** (axis A.1, A.3) or a **duplication debt** (A.2, A.4) that constrains the execution order of the C1 refactor: three of them (A.1, A.2, A.4) require a shared module to be shipped **before** the individual files are extracted, otherwise duplication is frozen into the new tree.

### A.1 — Structurally circular triangle `api ↔ tasks ↔ services`

- **Affected files**: §1 (`api/subscriptions.py:783, :1045`), §2 (`tasks/email_sync.py:156, :157, :487`), §3 (`api/auth.py:86`) — plus the out-of-scope caller `api/mailboxes.py:355, :474`.
- **Finding**: 8 "lazy" intra-function imports (7 of which are architecturally meaningful; the 8th at `auth.py:672` is a dead duplicate of `verify_password` already imported at the top, and the one at `email_templates.py:463` only imports `datetime`) trace a circular dependency triangle between the three layers: the `api` layer reaches back into `tasks` code (`update_subscription_statuses`, `sync_mailbox_emails`) and into `services` (`renewal_calculator`, `invite_token` model), while `tasks/email_sync` reaches back into 3 AI services (`ai_classifier`, `subscription_extractor`, `reference_extractor`) — which themselves consume the shared ORM models. The notable fact is that **every production caller of `email_sync` uses a lazy import** (`api/mailboxes.py` × 2, `api/subscriptions.py` × 1): that is the diagnostic, not the exception. No top-level cross-layer imports (`grep -rE '^from app\.(api|tasks)' services/ tasks/` returns zero results) — all circularity is resolved through function-level imports.
- **Impact on C1**: constrains the refactor order. Extracting `tasks/email_sync.py` first without introducing an interface seam (an `app/services/email_pipeline_protocol.py` or similar) would only **move** the lazy imports into the new sub-modules. The §2 split must therefore either (a) introduce a shared types/protocols module that `api`, `tasks`, and the AI services can import without a cycle, or (b) switch the AI services to dependency injection (passed as arguments to `_sync_mailbox_async` rather than imported) — which also makes them mockable and incidentally fixes the poor testability of the inner pipeline (§2 "~600 untested lines"). Without this prerequisite, the §2 split would freeze the 3 lazy imports inside `stages/classification.py` and `stages/extraction.py`.

### A.2 — Duplicated business logic from missing shared utilities

- **Affected files**: §1 (`api/subscriptions.py:207-217, :229-236, :327-338, :436-507, :595-599, :1406-1411`), §2 (`tasks/email_sync.py:374-394, :602-625, :647-661, :441-576, :298-302, :401-408, :420-427, :772-799`), §3 (`api/auth.py:184-198, :308-321, :821-836, :1173-1185`).
- **Finding**: **three axes of business-logic duplication** converge on the same root cause — the absence of a shared utility layer between the `api` and `tasks` layers. (a) **Subscription cost projection** (formulas `amount * 12`, `amount / 12`, `amount * 4.33`, `amount / 3`, `amount / 6`) repeated 3 times in `api/subscriptions.py` (stats, analytics-trends × 2). (b) **Price-change arithmetic** (`(new - old) / old * 100`, `"increase"/"decrease"` classification, `PriceHistory` instantiation) repeated 3 times in `tasks/email_sync.py` (AI-flagged path, post-hoc, initial). (c) **Deduplication policy**: §1 encodes 71 lines of heuristic scoring in `find_duplicate_subscriptions` (sender similarity, fuzzy provider match, amount ±5%, billing cycle, period); §2 encodes 115 lines of multi-level strategy (service references → email_sender → custom_label keywords → fallback) with a hardcoded list of payment processors (`paypal/stripe/paddle/gumroad/fastspring`). Both files also manipulate the `subscription_emails` association table via raw SQL (13 hits in §1, 5 hits in §2) without ever going through the ORM relation `Subscription.emails`. (d) **Auth email-dispatch boilerplate**: the `EmailService(db).send_*` block + `(success, error)` unpacking + `raise HTTPException(500, "...try resending")` is duplicated 4 times in `api/auth.py` (register, login OTP, 2FA setup, resend-verification).
- **Impact on C1**: blocks §B on the PR sequence. Three shared utilities must be extracted **before** splitting §1 and §2 — otherwise each sub-module inherits its local copy and the DRY gain is lost:
  - `app/services/cost_projection.py` (~40 lines) consumed by the future `api/subscriptions/stats.py` and `analytics.py`.
  - `app/services/price_history_recorder.py` (~90 lines, mentioned in §2 "Blocks") consumed by the future `tasks/email_sync/price_history.py` and `api/subscriptions/merge_split.py`.
  - `app/services/dedup_strategy.py` (consolidates the 71+115 lines; mentioned in §2) consumed by `api/subscriptions/duplicates.py` and `tasks/email_sync/persistence.py`.
  - `app/api/auth/_email_dispatch.py` (§3 internal helper, ~60 lines) collapses the 4 identical blocks.

### A.3 — Responsibilities co-located outside their layer in each file

- **Affected files**: all five — §1 (API doing repository work: raw SQL `subscription_emails.update()` at lines 597 and 1407), §2 (Celery task doing extraction-pipeline work: `_sync_mailbox_async` 820 lines mixing transport, classification, extraction, dedup, persistence, progress tracking), §3 (API driving 5 `app.security.*` sub-modules directly: `TOTPManager`, `EmailOTPManager`, `BackupCodesManager`, `VerificationRateLimiter`, `events` — instead of a `TwoFactorAuth` facade), §4 (HTML template embedding its own CSS duplicated 3 times: not a layer mix but a concern mix — layout / styles / sections), §5 (Resend transport + 5 typed wrappers + 3 inline HTML templates + module-level singleton).
- **Finding**: each audited file co-locates at least **two concerns** that should live in distinct layers. The most acute case is §2 (820-line orchestrator grouping 8 stages numbered in `# STAGE 1/2/3` comments but never reified into modules); the most structural is §1 (API layer short-circuiting the ORM relation to write directly into the association table — preventing any contract test via `Subscription.emails`); the most systemic is §3 (the `TwoFactorAuth` facade exists in `app.security.two_factor` but the API imports the 3 managers separately, so the abstraction leaks at every 2FA endpoint).
- **Impact on C1**: justifies **grouping by flow** rather than by HTTP verb in the proposed splits (§1, §3) and **grouping by pipeline stage** in §2. A side benefit: each seam thus exposed becomes a natural injection point for the missing characterisation tests (cf. A.5). Crucially, §3 calls for closing the `TwoFactorAuth` abstraction leak **in the same PR** as the file split — otherwise `api/auth/two_factor.py` will continue to import the 3 managers separately and the split will yield no coupling gain.

### A.4 — Inconsistent `rendering` / `delivery` boundary for outbound emails

- **Affected files**: §4 (`services/email_templates.py` — 3 externalised templates), §5 (`services/email_service.py:287-778` — 3 inline templates); plus 5 out-of-scope Celery tasks that mix HTML rendering and dispatch: `tasks/budget_alerts.py` (8 HTML tags), `tasks/renewal_reminders.py` (10), `tasks/trial_reminders.py` (13), `tasks/system_announcements.py` (10), `tasks/price_change_monitor.py` (13).
- **Finding**: the split between "HTML rendering" and "Resend delivery" is half-implemented. `email_templates.py` hosts 3 templates (`generate_summary_email`, `generate_2fa_otp_email`, `generate_email_verification_email`), but `email_service.py` hosts **3 additional inline templates** (`_get_renewal_reminder_template`, `_get_weekly_summary_template`, `_get_monthly_summary_template`) accounting for ~63% of the file's volume (490 of 782 lines) — as much HTML as in `email_templates.py` itself. Worse, the 5 peripheral Celery tasks render their HTML **directly inside the task code** instead of using `EmailTemplates`, adding ~54 HTML-tag occurrences cumulated across 5 files. And the same brand CSS (gradient `#667eea → #764ba2`, 600px container, SubTracker footer, font stack) is duplicated across all these sites — at least 8 non-DRY copies, not counting §4 (which already has 3 internal copies).
- **Impact on C1**: §4 and §5 must be refactored **together** (not in two separate PRs) to avoid freezing an even more fragmented intermediate state. The consolidated proposal (§5) — a `services/email/templates/` package absorbing both the 3 templates of §4, the 3 inline templates of §5, **and** the inline renderings of the 5 peripheral tasks — is a cross-cutting effort that extends the C1 perimeter. The `email_service = EmailService()` singleton (cf. A.6) must also disappear in the same move, otherwise the `transport` / `templates` separation remains polluted by a global stateful object.

### A.5 — Missing characterisation tests on mutation-critical paths

- **Affected files**: §1 (6 untested mutation routes: `find_duplicate_subscriptions`, `merge_subscriptions`, `update_subscription_renewal_status`, `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion`, `split_subscription`), §2 (~600 uncovered inner-pipeline lines: multi-strategy dedup, 3 price-history paths, renewal step, cancellation suggestion, cancellation polling, association-table writes), §3 (14 of 19 routes without endpoint tests: 2FA × 7, account management × 6, email verification × 1).
- **Finding**: it is the **same pattern across the three files** — the outer shell is tested (basic CRUD, login, refresh, isolated helpers), but the mutation-critical paths are left without a harness. And this is not coincidental: the 600 untested lines of §2 correspond to the same surface (subscription-mutating) as the 6 untested routes of §1 (merge, split, renewal-reconciliation), via the shared `update_subscription_statuses` function exported from §2 to §1 (§1 line 783). The 7 untested 2FA endpoints of §3 mutate `User.two_factor_enabled`, `User.backup_codes`, `User.totp_secret` — the most security-critical fields of the #1 god-node in the graph (`User`, 1019 edges).
- **Impact on C1**: characterisation tests = **prerequisite**, not optional. The §B plan must sequence **"write tests → split"** for §1, §2, and §3, with no overlap. Practical mitigation: for §2 specifically, the risk of hoisting a `db.commit()` outside the per-email scope requires a fixture that counts commits/rollbacks to verify transactional parity (§2 "Mitigation"). For §1/§3, response tests + assertions on DB side-effects and security-event logs are sufficient. This test debt accounts for most of the `L` effort in §2 (12-16h estimated, including 4h dedicated to characterisation tests) and half of the `M` effort in §1 and §3.

### A.6 — Singletons de module et fuite de configuration

- **Affected files**: §5 (`services/email_service.py:782` — `email_service = EmailService()`); pattern also observed in `services/push_notification_service.py:171` (out of scope, but evidence that it recurs on the services side).
- **Finding**: module-level instantiation happens **without a `db: Session`**, forcing `EmailService.__init__` to always fall back on `get_config_value(..., db=None)` — i.e. on environment variables, never on the `app_config` table. The constructor's `db` parameter, intended to allow a per-tenant read of the Resend config (`from`-headers, signing domain), is in fact neutralised at import time. The 8 importers (`tasks/budget_alerts.py`, `tasks/renewal_reminders.py`, `tasks/trial_reminders.py`, `tasks/summary_tasks.py`, `tasks/system_announcements.py`, `tasks/price_change_monitor.py`, `api/auth.py`, `services/notification_service.py`) all consume the singleton — so none can benefit from a DB-driven config.
- **Impact on C1**: blocks the `transport` / `templates` separation proposed in §5. Before splitting §5, either (a) remove the singleton and let each caller do `EmailService(db)` (acceptable if the 8 sites already pass a `db`), or (b) introduce a `get_email_service(db: Session)` factory returning a per-request instance. Option (a) is simpler if the call-sites allow it; otherwise (b) imposes a mini-migration of the 8 sites before the split. This point is not blocking for §1-§4 but must be decided in the PR that executes §5.

## §B — Prioritised roadmap

This section orders sub-project C1 into **8 phases** derived from §1-§5 (effort × risk × impact) and constrained by §A. The ordering follows a deliberate test-first, smallest-leverage-first cadence: **Phase 1** locks in the safety net (chartests for the §1 merge/split paths and the §2 sync pipeline) before any extraction code is written; **Phase 2** extracts `dedup_strategy.py` early as the highest-leverage shared module ("the brain"); **Phase 3** dissolves the `EmailService` module-level singleton ahead of any further test work, so global state stops poisoning the unit tests downstream; **Phase 4** extracts the three remaining shared utilities; **Phases 5-8** then handle the per-file splits (§4+§5 first per A.4, then §1, §3, §2 — §2 last because of A.1 + the 600 untested LoC).

> **No refactor code lands before Phase 1 chartests are green and stable.** This is the gate. A partial Phase 1 (some chartests merged, others skipped) invalidates everything that follows.

### Phase 1 — Safety net (chartests for §1 merge/split + §2 sync pipeline)

- **Affected files**: NEW tests in `backend/tests/` only. No production code changed.
- **Why first**: §A.5 says the untested mutation paths gate every extraction. The two zones with the highest blast radius are §1's `merge_subscriptions` / `split_subscription` (raw SQL on the `subscription_emails` association table) and §2's `_sync_mailbox_async` inner pipeline (~600 untested LoC: multi-strategy dedup, 3 price-history paths, cancellation polling, per-email commit boundaries). Locking these paths before any extraction means subsequent phases can refactor without fear of silent regressions on production data.
- **Effort**: **M** (~4-7h) — the dominant cost is the §2 fixture that counts `db.commit()` / `db.rollback()` for transactional parity, plus end-to-end cancellation tests that assert already-persisted subs survive while in-flight ones are rolled back.
- **Risk**: **low** — purely additive, captures current behaviour without modifying it. If a chartest reveals a pre-existing bug, escalate before "fixing" it (fixing in Phase 1 voids the contract the later phases depend on).
- **Dependencies**: _None._ Independent and can start immediately.
- **Concrete steps**:
  1. **§1 chartests (6 routes)**: `merge_subscriptions`, `split_subscription`, `find_duplicate_subscriptions`, `update_subscription_renewal_status`, `accept_cancellation_suggestion`, `dismiss_cancellation_suggestion`. Assertions: DB side-effects on `subscriptions`, `email_processing_records`, and the `subscription_emails` association table.
  2. **§2 inner-pipeline chartests**: multi-strategy dedup (service-reference → email_sender → custom_label → fallback), the 3 price-history paths (initial, update, change), renewal step, cancellation step, cancellation polling. Include the `commits/rollbacks` counter fixture (cf. §2 "Mitigation").
  3. **End-to-end cancellation test**: dispatch a cancellation request mid-batch; assert (a) already-persisted subscriptions survive, (b) the in-flight email is rolled back, (c) the mailbox status reflects the cancellation.
- **Note**: §3 chartests (14 untested routes including 7 2FA) are **not** in this phase. They land just-in-time before Phase 7 (the §3 split). Including them here would delay the start of refactor work without compounding benefit, since §3 paths touch security primitives that already have their own coverage in `test_auth.py`.

### Phase 2 — Extract `dedup_strategy.py` (the brain)

- **Affected files**: NEW `backend/app/services/dedup_strategy.py`. Two callers updated: `backend/app/api/subscriptions.py` and `backend/app/tasks/email_sync.py` (one inline block each replaced by a delegation).
- **Why second**: this is the single highest-leverage shared module — ~186 LoC consolidated from §1 (`find_duplicate_subscriptions`, ~71 lines) and §2 (multi-strategy dedup, ~115 lines). Once isolated and unit-tested, both call sites become near-cosmetic, and the module becomes a stable target for future maturity (e.g. when service-reference matching graduates from heuristic to deterministic). Doing it second — right after Phase 1 — validates the shared-module extraction pattern on the largest fish before the smaller ones in Phase 4.
- **Effort**: **M** (~3-5h) — extraction + unit tests on the new module + integration on the 2 call sites. Phase 1 chartests guarantee no regression.
- **Risk**: **low** — Phase 1 chartests cover both call sites end-to-end; the new module has its own unit tests covering the scoring matrix and threshold logic.
- **Dependencies**: **Phase 1 complete.**
- **Concrete steps**:
  1. Create `dedup_strategy.py` with the consolidated API: `score_duplicate_pair(a, b) -> int` (heuristic 100-point matrix from §1) and `find_best_match(candidate, pool, *, threshold=70) -> Optional[Subscription]` (multi-strategy from §2). Include the `paypal/stripe/paddle/gumroad/fastspring` payment-processor list as a module-level constant.
  2. Add unit tests covering: identical pair → 100, completely different → 0, partial matches at the threshold boundary (69 vs 70), the multi-strategy ordering when service-reference is present vs absent, the PayPal-as-payment-processor disambiguation case.
  3. Replace `find_duplicate_subscriptions` body in `api/subscriptions.py` with a delegation to `dedup_strategy.find_best_match` (≈ 71 lines removed).
  4. Replace the multi-strategy block in `_sync_mailbox_async` (`tasks/email_sync.py:441-576`) with a delegation (≈ 115 lines removed).
  5. Re-run Phase 1 chartests. They must pass unchanged.

### Phase 3 — Kill the `EmailService` module-level singleton

- **Affected files**: `backend/app/services/email_service.py` (singleton removed). All ~8 importers updated to use the new factory / DI pattern.
- **Why third**: per A.6, `email_service = EmailService()` is instantiated at module load with no `db` available, partially neutralising the constructor's `db` parameter and forcing env-var fallback. Concretely, this means **every test that touches an email path has to monkey-patch this global** — making unit tests fragile and integration tests order-dependent. Killing it now (before any further test work or refactor that touches email paths) means everything from Phase 4 onwards is testable cleanly. §3 (auth) in particular calls `email_service.send_*` for 2FA OTP and verification — Phase 7 will need clean tests there.
- **Effort**: **S-M** (~2-4h) — small surface (8 importers, all in `app/`), mechanical change once the pattern is decided.
- **Risk**: **medium** — touches many files, but each touch is straightforward. Mitigation: existing `test_auth.py` covers most send paths; Phase 1 chartests cover the rest indirectly.
- **Dependencies**: **Phase 1 complete** (the chartests provide the safety net for any send path we accidentally affect).
- **Concrete steps**:
  1. Decide between two patterns and pick one in this PR:
     - **(a) Factory function**: `def get_email_service(db: Session) -> EmailService` instantiates per call.
     - **(b) FastAPI dependency**: `EmailServiceDep = Annotated[EmailService, Depends(get_email_service)]` wired at router level for HTTP code paths; explicit `EmailService(db)` instantiation for Celery / non-HTTP code paths.
     - **Recommendation**: (b) for HTTP code (cleaner), (a) as fallback for tasks/services that don't go through FastAPI.
  2. Remove the module-level `email_service = EmailService()` line at the bottom of `email_service.py`.
  3. Update the 8 importers (likely `notification_service.py`, `tasks/{trial_reminders,renewal_reminders,price_change_monitor,budget_alerts,system_announcements,summary_tasks,email_verification}.py`, plus any `api/auth.py` direct uses).
  4. Re-run the existing test suite + Phase 1 chartests. All must pass.

### Phase 4 — Extract the remaining 3 shared utilities

- **Affected files**: NEW `backend/app/services/cost_projection.py`, NEW `backend/app/services/price_history_recorder.py`, NEW `backend/app/api/_email_dispatch.py`. Call sites updated: §1 (cost_projection × 3 sites), §2 (price_history_recorder × 3 sites), §3 (_email_dispatch × 4 sites).
- **Why fourth**: applies the shared-module pattern (validated by Phase 2 on the biggest module) to the remaining three smaller utilities. Doing this **before** the per-file splits keeps the §A.2 invariant: shared code first, structural split second. Each module is small (S effort), so the total is modest.
- **Effort**: **~M total** (~3-5h for all three combined: S + S + S). Each is mechanical extraction guided by the Phase 1/2 patterns.
- **Risk**: **low** — additive, each call site is covered by Phase 1 chartests or existing test suites (§1's CRUD/stats are well-tested for cost_projection consumers; §2's price-history is now covered by Phase 1 chartests; §3's email dispatch is covered by `test_auth.py`).
- **Dependencies**: **Phases 1-3 complete.**
- **Concrete steps**:
  1. **`cost_projection.py` (S, ~2h)** — pure function `project_monthly_cost(amount, billing_cycle)` + `project_yearly_cost`, `project_weekly_cost` variants. Mechanical extraction of §1:207-217, :229-236, :327-338. Add unit tests on the cycle-conversion matrix.
  2. **`price_history_recorder.py` (S-M, ~2-3h)** — exposes `record_initial_price(sub, amount, currency, source)`, `record_price_update(sub, new_amount, ...)`, `record_price_change(sub, ...)`. Consolidates the 3 inline paths of `tasks/email_sync.py:374-394, :602-625, :647-661`. Will be reused by `api/subscriptions/merge_split.py` in Phase 6.
  3. **`_email_dispatch.py` (S, ~1-2h)** — internal helper at `app/api/_email_dispatch.py` exposing `build_verification_url`, `send_verification_email`, `send_2fa_otp` that encapsulate the `EmailService(db).send_*` + `(success, error)` unpacking + `HTTPException(500)` block duplicated 4× in §3:184-198, :308-321, :821-836, :1173-1185. Note: depends on Phase 3 (uses the new factory / DI pattern, not the dead singleton).

### Phase 5 — Consolidated `services/email/` refactor (§4 + §5, post-singleton)

- **Affected files**: §4 (`services/email_templates.py`) + §5 (`services/email_service.py`).
- **Why now**: §A.4 imposes the §4↔§5 coupling (rendering/delivery boundaries are inconsistent: 3 templates externalised in §4 + 3 inline templates in §5 + ~54 HTML tags in 5 peripheral Celery tasks). With the singleton already gone (Phase 3) and `EmailService` callable cleanly, this phase is now purely a structural reorganisation: split the templates into a use-case-based package, reduce `email_service.py` to a thin transport layer, drop dead code.
- **Effort**: **M** (~4-7h) — slightly less than the original bundled estimate because the singleton work is already done. Includes upfront HTML snapshot tests on the 3 inline templates of §5 before extraction.
- **Risk**: **low → medium** — §4 has ~90% behaviour-based test coverage and zero cross-layer leakage; §5 is medium because of the 8 importers and the lack of a direct test of `email_service.py` (mitigated by snapshot tests pre-extraction).
- **Dependencies**: **Phase 3 complete** (singleton).
- **Concrete steps**:
  1. Restructure `services/email_templates.py` into a `services/email/templates/` package with `_styles.py` (factors out the 3× duplicated CSS), `summary.py`, `otp_2fa.py`, `verification.py`. `EmailTemplates` facade re-exported from `__init__.py` for backward compatibility.
  2. Snapshot-test the 3 inline templates of `email_service.py:287-778` against fixture data before any extraction.
  3. Extract those 3 templates into `services/email/templates/{renewal_reminder,weekly_summary,monthly_summary}.py`.
  4. Reduce `email_service.py` to `services/email/transport.py` (~80 lines: `send_email` + Resend config only). Remove the 5 dead typed wrappers (`send_renewal_reminder`, `send_weekly_summary`, `send_monthly_summary`).
  5. Migrate `notification_service.py:118, :136, :145` (sole caller of the removed wrappers) to the `EmailTemplates.* + transport.send_email` pattern.
  6. **Explicitly out-of-scope but flagged for §C**: the ~54 inline HTML tags in `tasks/{budget_alerts,renewal_reminders,trial_reminders,system_announcements,price_change_monitor}.py` are a natural extension after Phase 5, to be handled in C2.

### Phase 6 — Refactor `api/subscriptions/` (§1)

- **Affected files**: §1 (`api/subscriptions.py` → `api/subscriptions/{router,crud,stats,analytics,duplicates,merge_split,status_reconcile,feedback,price_history,cancellation_suggestion}.py`).
- **Why now**: §1 consumes 3 of the 4 modules already in place (`cost_projection`, `dedup_strategy`, `price_history_recorder` via merge), so this phase validates those modules on the most-tested surface (CRUD/stats/analytics already have ~65% coverage). §1 is also an import-DAG leaf (only `main.py` imports it): zero risk of cross-module regression outside the sub-package itself.
- **Effort**: **M** (~4-6h) — 60% mechanical thanks to existing coverage; the 6 mutation routes are protected by Phase 1 chartests.
- **Risk**: **medium** — the merge/split paths mutate `subscription_emails` in raw SQL, but are now protected by Phase 1 chartests. The `cost_projection`, `dedup_strategy`, `price_history_recorder` helpers being independently tested in Phases 2 & 4, their integration here is mechanical.
- **Dependencies**: **Phases 1, 2, 4 complete** (chartests + dedup_strategy + cost_projection + price_history_recorder).
- **Concrete steps**:
  1. Scaffold `api/subscriptions/` according to the §1 split.
  2. Move the tested CRUD/stats/analytics/duplicates endpoints (~60% of LoC).
  3. Wire `cost_projection.project_monthly_cost` into `stats.py` and `analytics.py` (eliminates the 3 duplications).
  4. Wire `dedup_strategy.score_duplicate_pair` into `duplicates.py` (already wired in Phase 2 — verify the delegation still holds after the split).
  5. Wire `price_history_recorder` into `merge_split.py`.
  6. Move `merge_subscriptions` and `split_subscription` (Phase 1 chartests provide the safety net).
  7. Collapse the 2 lazy imports of §1:783 (`update_subscription_statuses`) and §1:1045 (`RenewalCalculator`) into module-level imports inside `status_reconcile.py` — they were a false-positive triangle (cf. A.1), not a real cycle.

### Phase 7 — Refactor `api/auth/` (§3, with just-in-time chartests)

- **Affected files**: §3 (`api/auth.py` → `api/auth/{router,registration,login,two_factor,account,_email_dispatch}.py`). NEW chartests in `backend/tests/` for the 14 untested §3 routes.
- **Why now**: Phase 6 served as a dress rehearsal (split of a comparable-size router, DAG leaf, helpers consumed). With `_email_dispatch.py` already in place from Phase 4, only the splitting mechanics, the closing of the `TwoFactorAuth` abstraction leak (per A.3), and the just-in-time chartests for the 14 untested routes remain.
- **Effort**: **M-L** (~5-8h) — `M` for the split itself (consistent with §3) + `S-M` for the just-in-time chartests on 14 routes (7 2FA, 6 account-management, 2 email-verification). Defer-cost vs. Phase-1 estimate is small because §3 paths use security primitives that already have their own tests.
- **Risk**: **medium** — security-critical paths protected by the just-in-time chartests of this phase plus existing `test_auth.py` (35 tests, of which ~18 hit endpoints). Additional mitigation: assertions on the security-event logs in every chartest for side-effect parity.
- **Dependencies**: **Phase 4 complete** (`_email_dispatch.py`).
- **Concrete steps**:
  1. **Just-in-time chartests** (S-M): the 7 2FA endpoints (mutating `User.totp_secret`, `User.backup_codes`, `User.two_factor_enabled`), `verify_email` auto-login, `delete_account`, `change_password`, `update_preferences`, plus the language-preference endpoints. Include assertions on `security_events` rows.
  2. Scaffold `api/auth/` according to the §3 split.
  3. Move registration / login / refresh / me / logout (already covered by the 35 existing tests).
  4. Wire `_email_dispatch.py` into 4 sites: `register`, `login` OTP, `2fa/setup`, `resend-verification` (collapses 4 identical blocks into 1 helper, ~50 net line reduction).
  5. Move the 7 2FA endpoints into `two_factor.py` (just-in-time chartests provide the safety net).
  6. **Close the `TwoFactorAuth` abstraction leak** (per A.3): `two_factor.py` must import **only** `TwoFactorAuth` from `app.security.two_factor`, not the 3 separate managers (`TOTPManager`, `EmailOTPManager`, `BackupCodesManager`). Without this step, the split yields no coupling gain.
  7. Remove the dead duplicate `from app.security.password import verify_password` at §3:672 (already imported at the top, line 35).
  8. The dual "language" preference system (§3 lines 562-652: JSONB `settings` + dedicated `preferred_language` column) is noted for §C — not resolved in this phase.

### Phase 8 — Refactor `tasks/email_sync/` (§2, with interface seam)

- **Affected files**: §2 (`tasks/email_sync.py` → `tasks/email_sync/{celery_tasks,orchestrator,stages/*,price_history,renewal_step,cancellation_step,progress_tracker,filters,status_reconciler}.py`). NEW `app/services/email_pipeline_protocol.py`.
- **Why last**: this is the only L+high-risk file in the set. Must absorb the heaviest §A constraints simultaneously: (A.1) introduce the interface seam to break the `api ↔ tasks ↔ services` triangle; (A.2) consume `dedup_strategy.py` (Phase 2) + `price_history_recorder.py` (Phase 4); (A.3) reify the 3 stages already commented in the code but never modularised; (A.5) survive 600 lines of untested business logic *even after* the Phase 1 chartests (which cover the critical paths but not 100%). Doing §2 last maximises the ROI: `dedup_strategy.py` and `price_history_recorder.py` will have been through Phase 6 before landing here, and will have absorbed corner-cases.
- **Effort**: **L** (~12-16h) — including ~4h for *additional* chartests on the most exotic paths (commit boundaries beyond the Phase 1 fixture, `db.refresh(mailbox)` cancellation polling subtleties, residual `subscription_emails` writes) which are not all covered by Phase 1.
- **Risk**: **high** — code on the data-write path for the 4 most-connected graph entities (`Subscription` 816 edges, `Mailbox` 305, `PriceHistory` 148, `EmailMessage` 136). The 5-level-deep `try/except` + implicit per-email commits mean that **hoisting a commit out of the per-email scope batch-corrupts rollback semantics**.
- **Dependencies**: **Phases 1, 2, 4, 6 complete.**
- **Concrete steps**:
  1. **Introduce the interface seam** (resolves A.1): create `app/services/email_pipeline_protocol.py` defining Protocols for `AIClassifier`, `SubscriptionExtractor`, `ReferenceExtractor`. `_sync_mailbox_async` accepts these protocols **by injection** rather than importing them lazily at §2:156-157, :487. Secondary benefit: the inner pipeline becomes mockable, unblocking tests for the 600 uncovered lines.
  2. Scaffold `tasks/email_sync/` according to the §2 split, with an `__init__.py` that re-exports `sync_mailbox_emails`, `check_scheduled_syncs`, `update_subscription_statuses`, `parse_date_filter` for backward compatibility with the 3 callers (`api/mailboxes.py`, `api/subscriptions.py`, `tests/test_email_sync.py`).
  3. Move the tested helpers first: `parse_date_filter`, `update_subscription_statuses`, `DatabaseTask`, `filter_subscription_data`.
  4. Wire `dedup_strategy.py` (Phase 2) into `stages/persistence.py` — verify the delegation still holds after the split.
  5. Wire `price_history_recorder.py` (Phase 4) into `price_history.py` — collapses any remaining inline paths.
  6. Extract `progress_tracker.py` — the trickiest portion since it touches commit boundaries. Continually verify the Phase 1 commits/rollbacks counter fixture.
  7. Extract `stages/{classification,extraction,persistence}.py` — each stage becomes independently mockable thanks to the Protocols introduced in step 1.
  8. Collapse the 3 lazy imports of §2:156, :157, :487 into module-level imports inside `stages/classification.py` and `stages/extraction.py` (the interface seam neutralises them).

### Total estimated effort

- Phase 1: **M** (~4-7h) — safety-net chartests for §1 + §2.
- Phase 2: **M** (~3-5h) — `dedup_strategy.py`.
- Phase 3: **S-M** (~2-4h) — `EmailService` singleton kill.
- Phase 4: **~M total** (~3-5h) — 3 remaining shared utilities.
- Phase 5: **M** (~4-7h) — §4+§5 consolidated, post-singleton.
- Phase 6: **M** (~4-6h) — §1 split.
- Phase 7: **M-L** (~5-8h) — §3 split with just-in-time chartests.
- Phase 8: **L** (~12-16h) — §2 split + A.1 interface seam.

**Total: ~37-58 hours of focused refactor work** (≈ 1.5-2 weeks of full-time development, in practice spread over 3-4 sprints to preserve review quality and let integration tests run in pre-prod between phases).

### Caveats

- **Phase 1 must be 100% complete before any extraction work.** If Phase 1 reveals a pre-existing bug in §1 or §2, escalate before "fixing" it — fixing in Phase 1 voids the contract subsequent phases depend on. A partial Phase 1 (e.g. §1 chartests merged but §2 sync-pipeline chartests skipped) invalidates the Phase 8 safety net entirely.
- **Phase 5 (§4+§5) cannot be split.** Per A.4, shipping §4 without §5 or vice versa would leave the code in an *even more* fragmented state (3 externalised templates + 3 inline + transport layer half-extracted) than today. Both files must land in the same PR or in an uninterrupted chain of PRs.
- **Phase 8's interface seam (A.1) is an architectural investment worth isolating.** If Phase 8 exceeds 16h, split into two PRs: (8a) interface seam alone, validated by re-routing the lazy imports through the Protocols without moving the code; (8b) sub-module split. (8a) is independently shippable and improves testability even if (8b) is deferred.
- **Phases 6 and 7 can be shipped in parallel** if team capacity allows: they touch independent files (api/subscriptions.py vs api/auth.py), consume different shared modules (cost_projection/price_history_recorder vs _email_dispatch), and have no bidirectional dependency. The linear sequence proposed is defensive — it favours incremental validation of the shared modules on §1 before committing them on §3.
- **The ~54 HTML tags in the 5 peripheral Celery tasks** (`tasks/{budget_alerts,renewal_reminders,trial_reminders,system_announcements,price_change_monitor}.py`) are **not in C1**. That work is a natural continuation after Phase 5 (`services/email/templates/` consolidation), to be scoped in C2 with its own roadmap.
- **The dual "language" preference system in §3** (JSONB `settings` + `preferred_language` column) is not resolved by the split: this is a schema debate to handle separately (cf. §C).

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
