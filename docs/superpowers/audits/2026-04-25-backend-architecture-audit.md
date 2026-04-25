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

_Pending audit._

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
