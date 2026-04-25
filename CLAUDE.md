# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Subscription Tracker** - A multi-user SaaS web application that automatically discovers and tracks subscriptions by analyzing emails from connected mailboxes using AI-powered extraction.

**Key Features:**
- Email integration (JMAP/Gmail/Outlook OAuth)
- AI-powered subscription detection and extraction
- Multi-language support (French/English)
- Intelligent deduplication
- Budget tracking and spending analytics
- Confidence-based routing with manual review

## Tech Stack

**Frontend:**
- React 18+ with TypeScript
- Chakra UI for components
- React Query + Context API for state
- Recharts for analytics
- Vite for build tooling

**Backend:**
- Python 3.11+ with FastAPI
- SQLAlchemy 2.0 ORM
- PostgreSQL 15+ database
- Celery 5+ for background jobs
- Redis for broker/cache
- OpenAI GPT-4o-mini for AI extraction

**DevOps:**
- Docker Compose for development
- Separate dev/prod configurations
- Hot-reload enabled for development

## Git Workflow Rules (MANDATORY)

### Branch Policy
- **NEVER push directly to `main`** - Always create a feature branch and PR
- Only push to `main` after explicit user validation with a stated reason
- Feature branches should follow naming: `feature/description`, `fix/description`, `hotfix/description`

### Pre-Commit Checklist (run before EVERY commit)
1. **Backend linting** (required):
   ```bash
   docker-compose -f docker-compose.dev.yml exec backend python -m black --check app/
   docker-compose -f docker-compose.dev.yml exec backend python -m flake8 app/ --max-line-length=120
   ```
   If black fails, fix with:
   ```bash
   docker-compose -f docker-compose.dev.yml exec backend python -m black app/
   ```

2. **Frontend linting** (required):
   ```bash
   cd frontend && npm run lint
   ```

3. Only commit after all linters pass (warnings are acceptable, errors are not)

### PR Workflow
1. Create feature branch from `main`
2. Make changes and run linters
3. Commit with descriptive message
4. Push feature branch
5. Create PR with summary and test plan
6. Wait for user approval before merging

## Daily Commands

```bash
# Logs
docker-compose -f docker-compose.dev.yml logs -f backend
docker-compose -f docker-compose.dev.yml logs -f celery_worker

# Restart (triggers hot-reload)
docker-compose -f docker-compose.dev.yml restart backend

# Migrations
docker-compose exec backend alembic revision --autogenerate -m "description"
docker-compose exec backend alembic upgrade head
docker-compose exec backend alembic downgrade -1

# Database access
docker-compose exec postgres psql -U postgres -d subscription_tracker

# Tests
docker-compose exec backend pytest
docker-compose exec frontend npm test

# Install dependencies
docker-compose exec backend pip install <package>  # then update backend/requirements.txt
docker-compose exec frontend npm install <package>
```

For setup, deployment, backups, see `docs/operations/`.
For ad-hoc / less-frequent commands, see `docs/operations/commands.md`.

## Slash Commands

Project-scoped slash commands live in `.claude/commands/`:

- `/precommit` — full pre-commit checklist (lint, format, suggest commit msg)
- `/migrate <description>` — Alembic revision + safety review + upgrade
- `/restart-and-tail <service>` — restart docker service and watch logs 30s

## Architecture Snapshot

Email Processing Pipeline:

```
mailbox → fetch (batch 100) → classify (template/AI) →
extract (template/AI) → dedup (multi-factor score) →
confidence routing (>85% auto / 50-84% review / <50% reject) → save
```

Code layout:

```
backend/
├── app/
│   ├── api/              # FastAPI route handlers (prefixed /api/)
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic (EmailProcessor, AIService, …)
│   ├── tasks/            # Celery tasks
│   ├── email_providers/  # Provider interface + JMAP/Gmail/Outlook impl
│   ├── security/         # Auth, encryption, JWT
│   └── main.py           # FastAPI app init
├── alembic/              # DB migrations
└── tests/

frontend/src/
├── components/           # Organized by feature (auth, subscriptions, …)
├── hooks/                # useSubscriptions, useAuth, …
├── contexts/             # Auth, Settings
├── api/                  # API client
├── types/                # TypeScript types
└── utils/
```

Three critical design decisions (rationale in `docs/architecture/`):

- **OpenAI Assistant over direct API** — context-preserving, structured output, easier to update without code changes. See `docs/architecture/ai-strategy.md`.
- **Celery over simpler alternatives** — retries, monitoring, beat scheduler, horizontal scaling. See `docs/architecture/email-pipeline.md`.
- **Application-level filtering vs PostgreSQL RLS** — simpler now, can add RLS in Phase 4. See `docs/architecture/security.md`.

For everything else architectural, navigate `docs/architecture/`. Reading `graphify-out/GRAPH_REPORT.md` first is recommended for code-level questions.

## Documentation Index

| Need | Doc |
|---|---|
| Set up the project locally | `docs/setup.md` |
| Deploy to production | `docs/operations/deployment.md` |
| CI/CD pipeline | `docs/operations/ci-cd.md` |
| Backup / restore | `docs/operations/backup.md` |
| Email sync (backend & frontend) | `docs/operations/sync.md` |
| Ad-hoc shell commands & scripts/ inventory | `docs/operations/commands.md` |
| Architecture overview + Mermaid diagram | `docs/architecture/overview.md` |
| Database schema | `docs/architecture/data-model.md` |
| Email pipeline detail | `docs/architecture/email-pipeline.md` |
| AI / OpenAI Assistant | `docs/architecture/ai-strategy.md` |
| Subscription deduplication | `docs/architecture/deduplication.md` |
| Auth / JWT / encryption | `docs/architecture/auth.md` |
| REST API conventions | `docs/architecture/api-conventions.md` |
| Security model | `docs/architecture/security.md` |
| Push notifications backend | `docs/features/push-notifications.md` |
| Active roadmap | `docs/roadmap/current.md` |
| Mobile responsive roadmap | `docs/roadmap/mobile.md` |

## Conventions At-A-Glance

**API:**
- All endpoints prefixed `/api/`, RESTful resource naming.
- Consistent error responses with `detail` messages.
- Pagination via `page` + `page_size` for list endpoints.

**Database:**
- UUID primary keys on all tables.
- `created_at` / `updated_at` timestamps on most tables.
- Soft deletes via `is_active` boolean where applicable.
- JSONB for flexible / structured metadata.

**Auth & Security (in-depth in `docs/architecture/{auth,security}.md`):**
- bcrypt password hashing (auto salt).
- JWT access (30 min) + refresh (7 days), Bearer in `Authorization` header.
- Mailbox credentials Fernet-encrypted at rest (`ENCRYPTION_KEY` env var).
- Multi-tenancy enforced by `user_id` filters in queries (no PostgreSQL RLS yet).

## Common Gotchas

**Email Processing:**
- JMAP uses provider-specific email IDs — don't assume format.
- HTML emails need BeautifulSoup parsing; French date formats vary, AI handles.
- PayPal emails need special duplicate handling (see `docs/architecture/deduplication.md`).
- `subscriptions.custom_label` differentiates same-provider subs (e.g. Twitch streamers).
- `email_processing_records.extracted_data` is JSONB with raw extraction results.

**Database:**
- Always filter by `user_id` for multi-tenancy.
- Encrypted credentials must be decrypted before use (Fernet, key from env).
- JSONB fields need explicit casting in raw SQL.
- Run `alembic heads` if you suspect a migration conflict.

**Docker:**
- Volume mounts enable hot-reload.
- DB persists in named volume `postgres_data`.
- Restart backend container after dependency installs.
- Common port collisions: 5173 (frontend), 8000 (backend), 5432 (Postgres), 6379 (Redis).

**Frontend:**
- React Query caches 30s by default.
- WebSocket reconnection logic needed for job progress updates.
- Chakra UI requires ThemeProvider wrapper.

**Environment variables required:** `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `CORS_ORIGINS`. Generate `ENCRYPTION_KEY` with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

## File Conventions

- Backend tests: `backend/tests/`
- Frontend tests: co-located with components or `frontend/src/__tests__/`
- Utility scripts: `scripts/` (audit in `docs/operations/commands.md`)
- Claude-generated reports/analyses: `claudedocs/`
- Migrations: `backend/alembic/versions/`

## graphify

This project uses graphify for code dependency analysis at `graphify-out/`.

Rules:
- Before answering architecture or codebase questions, read `graphify-out/GRAPH_REPORT.md` for god nodes and community structure.
- If `graphify-out/wiki/index.md` exists, navigate it instead of reading raw files.
- The graph is auto-updated at session end if backend Python files were modified (Stop hook in `.claude/settings.json`).
