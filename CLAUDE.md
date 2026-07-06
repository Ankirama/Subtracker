# CLAUDE.md

Guidance for Claude Code when working in this repository. Cross-project rules (agent routing,
stack defaults, git/secret hygiene) are inherited from `~/.claude/CLAUDE.md`; this file and the
`@`-imported rules below hold **project-specific** context only. Heavy reference material lives
in `docs/` and is loaded **on demand** via the Documentation Index — read those files when the
task needs them rather than keeping everything in context.

## Project Overview

**Subscription Tracker** — a multi-user SaaS web app that automatically discovers and tracks
subscriptions by analyzing emails from connected mailboxes with AI-powered extraction.
Key features: email integration (JMAP/Gmail/Outlook OAuth), AI subscription detection,
FR/EN support, intelligent deduplication, budget analytics, confidence-based routing with
manual review.

**Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL + Celery/Redis + OpenAI on the backend;
React 18 + TypeScript + Chakra UI + React Query + Vite on the frontend; Docker Compose for dev.
Full detail and the architecture diagram: `docs/architecture/overview.md`.

## Always-on rules

@.claude/rules/conventions.md
@.claude/rules/env.md
@.claude/rules/security.md
@.claude/rules/git-workflow.md

## Way of working

This is an **agent-team** project. The main session orchestrates: understand → plan → delegate
to the right specialist agent (architect, backend, frontend, devsecops, test-qa, debugger,
code-reviewer, security-auditor, doc-writer — see `~/.claude/CLAUDE.md` for routing). Prefer
delegation over doing everything in the main thread.

Default flow: **`/ticket` → plan (architect) → implement → test → `/review` → `/commit` → `/pr`**.
Never push to `main` without explicit approval (see `.claude/rules/git-workflow.md`).

## Daily Commands

```bash
# Logs / restart (hot-reload)
docker-compose -f docker-compose.dev.yml logs -f backend
docker-compose -f docker-compose.dev.yml logs -f celery_worker
docker-compose -f docker-compose.dev.yml restart backend

# Migrations
docker-compose exec backend alembic revision --autogenerate -m "description"
docker-compose exec backend alembic upgrade head

# Tests
docker-compose exec backend pytest
docker-compose exec frontend npm test

# DB access
docker-compose exec postgres psql -U postgres -d subscription_tracker
```

Setup, deployment, backups: `docs/operations/`. Ad-hoc / rarer commands: `docs/operations/commands.md`.

## Slash Commands

Project-scoped commands live in `.claude/commands/`:
- `/precommit` — full pre-commit checklist (lint, format, suggest commit msg)
- `/migrate <description>` — Alembic revision + safety review + upgrade
- `/restart-and-tail <service>` — restart a docker service and watch logs 30s

## Documentation Index

Read these on demand — do not preload them.

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
| Set up locally / deploy / backup / CI-CD | `docs/setup.md`, `docs/operations/` |
| Email sync (backend & frontend) | `docs/operations/sync.md` |
| Roadmap (active / mobile) | `docs/roadmap/current.md`, `docs/roadmap/mobile.md` |
| Code-level dependency map | `graphify-out/GRAPH_REPORT.md` |

## File Conventions

- Backend tests: `backend/tests/` · Frontend tests: co-located or `frontend/src/__tests__/`
- Utility scripts: `scripts/` (inventory in `docs/operations/commands.md`)
- Claude-generated reports/analyses: `claudedocs/`
- Migrations: `backend/alembic/versions/`

## graphify

Code dependency graph at `graphify-out/`. Before architecture/codebase questions, read
`graphify-out/GRAPH_REPORT.md` (or navigate `graphify-out/wiki/index.md` if present) instead of
grepping raw files. The graph auto-updates at session end when backend Python files change
(Stop hook in `.claude/settings.json`).
