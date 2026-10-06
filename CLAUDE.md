# Project: Subscription Tracker

> Cross-project rules (agent routing, workflow, conventions, .env, security, bash hygiene)
> are inherited from `~/.claude/CLAUDE.md`. This file and the `@`-imported rules hold
> **project-specific** context only. Heavy reference material lives in `docs/` and is read
> **on demand** via the Documentation Index below — do not preload it.

A multi-user web app that discovers and tracks subscriptions by analyzing emails from
connected mailboxes with AI extraction. Features: mailbox integration (JMAP and Gmail OAuth;
Outlook is declared but **not implemented** — `api/mailboxes.py` returns "not yet
implemented"), AI subscription detection, FR/EN emails and UI, deduplication, budgets and
analytics, confidence-based routing with a manual review queue.

> **Critical invariant — multi-tenancy is application-level.** Every query must filter by
> `user_id`; there is no PostgreSQL RLS. A missing filter is a cross-user data leak.
> Mailbox credentials are Fernet-encrypted at rest. Details in `.claude/rules/security.md`.

## Stack

Deviates from the house defaults on every layer:
- **Backend: FastAPI**, not Django — SQLAlchemy 2.0 + Alembic, Pydantic v2 / pydantic-settings,
  PostgreSQL, Celery (worker + beat) on Redis, OpenAI. Python 3.11 in CI.
- **Frontend: React 18 + TypeScript strict + Vite + Chakra UI** (not Tailwind), React Query
  (`@tanstack/react-query`), i18n, PWA via `vite-plugin-pwa`. Tests: Vitest + React Testing
  Library + MSW (handlers in `frontend/src/test/`).
- **Lint: black + ruff (CI) / black + flake8 (pre-commit hook)** — not ruff-only. See
  `.claude/rules/conventions.md` for the drift.
- **Infra**: Docker Compose for dev (`docker-compose.dev.yml` only — there is no default
  `docker-compose.yml`); NAS deploy via Dockhand (`deploy/nas/`); images built to GHCR.

## Project-specific rules

@.claude/rules/conventions.md
@.claude/rules/env.md
@.claude/rules/security.md
@.claude/rules/git-workflow.md

## Architecture

Full detail and diagram: `docs/architecture/overview.md`.

- **API** (`backend/app/api/`): thin FastAPI routers, all under `/api/`. `subscriptions/` is a
  package split by concern (crud, duplicates, merge_split, analytics, …); `admin/` holds the
  admin panel endpoints.
- **Services** (`backend/app/services/`): business logic — AI classifier/extractor, dedup
  strategy, renewal calculator, budgets, notifications, sync-error classification/circuit breaker.
- **Email pipeline**: `backend/app/email_providers/` (JMAP, Gmail behind
  `EmailProviderInterface`) → Celery task `tasks/email_sync/` (orchestrator + stages:
  classification, persistence, cancellation step) → confidence routing (auto-accept ≥ 85,
  review ≥ 50, defaults from `DEFAULT_CONFIDENCE_*`). Detail: `docs/architecture/email-pipeline.md`.
- **Config**: `backend/app/config.py` (pydantic-settings, reads `.env`).

## Directory map

```
backend/app/          FastAPI app (api, services, models, schemas, tasks, security, middleware)
backend/alembic/      migrations (versions/)  — backend/migrations/ holds one legacy .sql file
backend/tests/        backend pytest suite
backend/scripts/      ad-hoc maintenance scripts (create_admin, generate_vapid_keys, …)
frontend/src/         React app; tests co-located as *.test.ts(x); test helpers in src/test/
deploy/nas/           NAS (Dockhand) compose + env template
scripts/              repo scripts: pre-commit hook, install-hooks, setup/quickstart
docs/                 architecture, operations, roadmap; docs/superpowers/{specs,plans,audits}
claudedocs/           reports Claude generates (also legacy backend/claudedocs/)
```

## Documentation Index

| Need | Doc |
|---|---|
| Architecture overview + diagram + code layout | `docs/architecture/overview.md` |
| Common gotchas (email, DB, docker, frontend) | `docs/development/gotchas.md` |
| Database schema | `docs/architecture/data-model.md` |
| Email pipeline detail | `docs/architecture/email-pipeline.md` |
| AI / OpenAI Assistant | `docs/architecture/ai-strategy.md` |
| Subscription deduplication | `docs/architecture/deduplication.md` |
| Auth / JWT / encryption | `docs/architecture/auth.md` |
| REST API conventions | `docs/architecture/api-conventions.md` |
| Security model | `docs/architecture/security.md` |
| Push notifications backend | `docs/features/push-notifications.md` |
| Set up the project locally | `docs/setup.md` |
| Deploy (NAS / Dockhand) + automatic backups | `docs/operations/deploy-nas-dockhand.md` |
| CI checks & GHCR image build | `docs/operations/ci-cd.md` |
| Email sync (backend & frontend) | `docs/operations/sync.md` |
| Ad-hoc / rarer commands, script inventory | `docs/operations/commands.md` |
| Roadmap (active / mobile) | `docs/roadmap/current.md`, `docs/roadmap/mobile.md` |

## Knowledge graph

This project is mapped with graphify (`graphify-out/`, gitignored). Before grepping or reading
many files, query the graph: `graphify query "<question>"`, or read
`graphify-out/GRAPH_REPORT.md`. Git hooks rebuild it on commit/checkout; a Stop hook
(`.claude/hooks/graphify-update.sh`) also rebuilds it when `backend/app/**/*.py` changed.
Manual rebuild: `graphify update .`. Exclusions live in `.graphifyignore`.

## Vault

Project note: `~/Nextcloud/hermes_brain/20_Projects/Active/Subscription Tracker.md` — decisions
and important events go into its `claude-managed` block via the `record` skill.

## Commands

All compose commands need `-f docker-compose.dev.yml` (no default compose file).

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f backend          # or celery_worker, celery_beat, frontend
docker compose -f docker-compose.dev.yml restart backend          # hot-reload otherwise

# Migrations
docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "description"
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head

# Tests
docker compose -f docker-compose.dev.yml exec backend pytest
npm --prefix frontend test -- --run

# Lint (what CI runs)
docker compose -f docker-compose.dev.yml exec backend black --check .
uvx ruff check backend        # ruff is not in requirements.txt / the image; CI pip-installs it
npm --prefix frontend run lint
npm --prefix frontend exec -- tsc --noEmit

# DB access
docker compose -f docker-compose.dev.yml exec postgres psql -U postgres -d subscription_tracker
```

Project slash commands (`.claude/commands/`): `/precommit` (lint + format + commit message),
`/migrate <description>` (Alembic revision + safety review + upgrade),
`/restart-and-tail <service>` (restart a service and watch logs 30 s).
