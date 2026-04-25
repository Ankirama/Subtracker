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

_Pending audit._

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
