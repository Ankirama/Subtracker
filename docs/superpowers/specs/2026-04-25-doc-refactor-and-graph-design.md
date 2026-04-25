# Doc Refactor & Resource Graph — Design

**Date**: 2026-04-25
**Status**: Approved (pending user review of this spec file)
**Author**: Brainstorming session — Fabien + Claude

## 1. Context & Problem

The `subscription_tracker` repo has accumulated **16 markdown files (~7,900 lines)** with significant duplication and unclear ownership:

- `AGENTS.md` is byte-identical to `CLAUDE.md` (literal duplicate).
- `SETUP.md`, `DEPLOYMENT.md`, `PRODUCTION_DEPLOYMENT.md`, `scripts/setup.sh`, `scripts/quickstart.sh` overlap.
- `SYNC_GUIDE.md` and `FRONTEND_SYNC_GUIDE.md` overlap.
- `SESSION_SUMMARY.md` is a dated artefact (2025-11-15) cluttering the root.
- `ROADMAP.md` and `docs/MOBILE_ROADMAP.md` are not consolidated.
- `TECHNICAL_SPEC.md` is a 2,240-line monolith (28% of total doc volume) — too large for selective Claude context loading.
- `CLAUDE.md` (auto-loaded every session) contains content that is rarely needed inline (specific SQL queries, detailed troubleshooting).

`graphify-out/` is referenced in `CLAUDE.md` but does not exist on disk (never generated).

There are also suspect duplicates in `scripts/` (e.g., `backup.sh` vs `backup_postgres.sh`, multiple `deploy*.sh`), but cleaning shell scripts is **out of scope** for this spec.

## 2. Goals & Non-Goals

### Goals

1. **Optimize the documentation set for Claude consumption**: minimize what is auto-loaded into every session, organize the rest into discoverable, single-source-of-truth documents.
2. **Establish a code dependency graph** as a navigation aid for future refactoring work and as a reference Claude can read on demand.
3. **Introduce 2–3 high-value Claude Code slash commands** to encode multi-step recurring workflows.

### Non-Goals (explicit, deferred to other sub-projects)

- Refactoring application code (`backend/app/`, `frontend/src/`).
- Performance optimisation (Celery, SQL queries, AI calls, React Query).
- Cleaning up `scripts/` shell duplicates beyond identifying them in a list.
- Changing CI/CD or deployment infrastructure.
- Generating frontend dependency graph (deferred, can be added later if useful).
- Mermaid data-flow / sequence diagrams (already covered textually in pipeline doc).

## 3. Guiding Principle

`CLAUDE.md` is auto-loaded into every session — it is **a permanent context cost**.
Everything else lives in `docs/` and is **loaded on demand** — cheap until needed.

The whole design optimises this trade-off: keep in `CLAUDE.md` what helps in 80% of sessions; push everything specialised to focused docs that can be loaded selectively.

## 4. Target File Structure

```
project-root/
├── README.md                       # public-facing, ~minimal kept as-is
├── CLAUDE.md                       # ~250 lines, hub pratique (see §6)
├── AGENTS.md                       # symlink → CLAUDE.md (Codex convention)
├── graphify-out/                   # generated, partially gitignored (see §8)
│   ├── GRAPH_REPORT.md             # COMMITTED
│   ├── wiki/                       # COMMITTED (markdown)
│   └── *.html, *.json, *.png       # GITIGNORED
└── docs/
    ├── index.md                    # NEW — table of contents for docs/
    ├── setup.md                    # ← ex SETUP.md
    ├── operations/
    │   ├── deployment.md           # ⊕ DEPLOYMENT.md + PRODUCTION_DEPLOYMENT.md
    │   ├── ci-cd.md                # ← ex docs/CI-CD-SETUP.md
    │   ├── backup.md               # ← ex BACKUP_GUIDE.md
    │   ├── sync.md                 # ⊕ SYNC_GUIDE.md + FRONTEND_SYNC_GUIDE.md
    │   └── commands.md             # NEW — ad-hoc commands + scripts/ reference + suspects audit
    ├── architecture/
    │   ├── overview.md             # NEW — high-level + Mermaid diagram (§7)
    │   ├── data-model.md           # ← extracted from TECHNICAL_SPEC.md
    │   ├── email-pipeline.md       # ← extracted from TECHNICAL_SPEC.md
    │   ├── ai-strategy.md          # ← extracted from TECHNICAL_SPEC.md
    │   ├── deduplication.md        # ← extracted from TECHNICAL_SPEC.md
    │   ├── auth.md                 # ⊕ AUTH_GUIDE.md + auth section of TECHNICAL_SPEC.md
    │   ├── api-conventions.md      # ← extracted from TECHNICAL_SPEC.md
    │   └── security.md             # ← extracted from TECHNICAL_SPEC.md
    ├── features/
    │   └── push-notifications.md   # ← ex docs/PUSH_NOTIFICATIONS_BACKEND.md
    ├── roadmap/
    │   ├── current.md              # ← ROADMAP.md (Phase 1 ✅ items moved to _archive)
    │   └── mobile.md               # ← ex docs/MOBILE_ROADMAP.md
    ├── superpowers/
    │   └── specs/                  # this directory
    └── _archive/
        ├── SESSION_SUMMARY-2025-11-15.md   # ← ex SESSION_SUMMARY.md
        └── roadmap-phase-1-completed.md    # ← Phase 1 ✅ items lifted from ROADMAP.md
```

`TECHNICAL_SPEC.md` **disappears as a file**; its content is redistributed into `docs/architecture/`. Nothing is lost, only reorganised by domain.

## 5. Migration Mapping (old → new)

Every existing `.md` file has a destination. No silent deletions.

| Source | Destination | Action |
|---|---|---|
| `AGENTS.md` | (root) | Replaced by symlink to `CLAUDE.md` |
| `CLAUDE.md` | (root) | Rewritten in place — see §6 |
| `README.md` | (root) | Kept as-is, untouched (public-facing) |
| `SETUP.md` | `docs/setup.md` | Moved, light edit |
| `DEPLOYMENT.md` | `docs/operations/deployment.md` | Merged with PRODUCTION_DEPLOYMENT.md |
| `PRODUCTION_DEPLOYMENT.md` | `docs/operations/deployment.md` | Merged into above |
| `BACKUP_GUIDE.md` | `docs/operations/backup.md` | Moved |
| `SYNC_GUIDE.md` | `docs/operations/sync.md` | Merged with FRONTEND_SYNC_GUIDE.md |
| `FRONTEND_SYNC_GUIDE.md` | `docs/operations/sync.md` | Merged into above |
| `AUTH_GUIDE.md` | `docs/architecture/auth.md` | Merged with TECHNICAL_SPEC auth section |
| `TECHNICAL_SPEC.md` | `docs/architecture/*.md` | Split into 7 focused files |
| `ROADMAP.md` | `docs/roadmap/current.md` + `docs/_archive/` | Active items kept, completed items archived |
| `SESSION_SUMMARY.md` | `docs/_archive/SESSION_SUMMARY-2025-11-15.md` | Archived |
| `docs/CI-CD-SETUP.md` | `docs/operations/ci-cd.md` | Moved |
| `docs/MOBILE_ROADMAP.md` | `docs/roadmap/mobile.md` | Moved |
| `docs/PUSH_NOTIFICATIONS_BACKEND.md` | `docs/features/push-notifications.md` | Moved |

## 6. CLAUDE.md Refactor (~400 → ~250 lines)

New `CLAUDE.md` outline (target line counts approximate):

| Section | Lines | Notes |
|---|---|---|
| 1. Project Overview | ~10 | Kept |
| 2. Tech Stack | ~15 | Kept |
| 3. Git Workflow Rules | ~20 | Kept verbatim — these are mandatory |
| 4. Daily Commands | ~50 | Top-80% commands inline (logs, restart, migrations, tests, db access) |
| 5. Slash Commands | ~10 | Pointer to `.claude/commands/` with one-line summary each |
| 6. Architecture Snapshot | ~40 | Pipeline + 3 critical decisions only; rest → `docs/architecture/` |
| 7. Doc Index | ~30 | Table: "need X → read `docs/Y.md`" |
| 8. Common Gotchas | ~30 | Top 10 only, the rest goes into respective domain docs |
| 9. File Conventions | ~10 | Where tests/scripts/docs live |
| 10. Graphify pointer | ~5 | Already present, preserved |

**Removed from `CLAUDE.md`** (moved to specialised docs):
- Detailed SQL queries (→ `docs/operations/commands.md`)
- Detailed auth/security implementation (→ `docs/architecture/auth.md` + `security.md`)
- OpenAI Assistant configuration (→ `docs/architecture/ai-strategy.md`)
- Phase Roadmap Context (→ `docs/roadmap/current.md`)
- Long troubleshooting list (→ keep top 10 in CLAUDE.md, rest distributed by domain)

## 7. Resource Graph (Sub-project B)

### 7.1 Code Dependency Graph (graphify)

- **Tool**: existing `graphify` skill (tree-sitter AST, Louvain communities).
- **Scope**: backend Python only (`backend/app/**/*.py`). Frontend deferred.
- **Output location**: `graphify-out/` at repo root (skill default).
- **Versioning policy** (in `.gitignore`):
  - **Committed**: `graphify-out/GRAPH_REPORT.md`, `graphify-out/wiki/*.md`
  - **Ignored**: `graphify-out/*.html`, `graphify-out/*.json`, `graphify-out/*.png` and any other binary assets.
- **Reference from CLAUDE.md**: existing pointer to `graphify-out/GRAPH_REPORT.md` is preserved; the rule already says "before answering architecture questions, read it first".

### 7.2 Architecture Diagram (Mermaid, static)

- **Location**: `docs/architecture/overview.md`.
- **Format**: Mermaid `flowchart` block.
- **Nodes**: Frontend (React), API (FastAPI), Celery Workers, PostgreSQL, Redis, OpenAI API, Email Providers (JMAP/Gmail/Outlook).
- **Edges**: HTTP/WebSocket, Celery task queues, DB connections, OAuth flows, AI calls.
- **Maintenance**: manual; updated when architecture changes.

## 8. Slash Commands

Three commands created in `.claude/commands/` (project-scoped):

### 8.1 `/precommit`

**File**: `.claude/commands/precommit.md`

Runs the full pre-commit checklist defined in `CLAUDE.md`:
1. Show `git status` and `git diff --staged`.
2. Run `docker-compose -f docker-compose.dev.yml exec backend python -m black --check app/`. If failures, run `black app/` to auto-fix and re-check.
3. Run `flake8 app/ --max-line-length=120` and surface errors (warnings non-blocking).
4. Run `cd frontend && npm run lint`.
5. If everything is clean, propose a commit message based on the staged diff (following CLAUDE.md commit conventions).
6. If any blocker remains, stop and list violations.

### 8.2 `/migrate <description>`

**File**: `.claude/commands/migrate.md`

Generates and applies an Alembic migration safely:
1. Run `docker-compose exec backend alembic revision --autogenerate -m "<description>"`.
2. Read the generated migration file. Review for known autogenerate pitfalls (column drops/renames, `NOT NULL` without default on existing tables, lost indexes, FK changes).
3. If review surfaces concerns, summarise them and ask the user to confirm before applying.
4. Otherwise run `docker-compose exec backend alembic upgrade head`.
5. On upgrade error, surface the SQL/exception and offer rollback (`alembic downgrade -1`).

### 8.3 `/restart-and-tail <service>`

**File**: `.claude/commands/restart-and-tail.md`

Restart a docker-compose service and watch logs briefly:
1. `docker-compose -f docker-compose.dev.yml restart <service>` (default service: `backend`).
2. Tail logs for ~30 seconds (`docker-compose logs -f --tail=50 <service>` with timeout).
3. Surface any ERROR / WARNING lines; if logs look clean, report "clean".

## 9. Graphify Auto-Update Hook

A `Stop` hook in `.claude/settings.json` that runs `graphify update .` once at session end **only if** any `backend/app/**/*.py` file changed during the session.

- **Why `Stop` and not `PostToolUse`**: avoids re-running on every file edit (Claude often edits many files in a row).
- **Why conditional on backend changes**: a session that only touched docs / frontend doesn't need a Python AST rebuild.
- **Failure policy**: best-effort. If `graphify update .` fails or is missing, log a one-line warning and exit non-blocking — never break the session end.

Concrete shell logic (sketch, to be finalised in implementation plan):
```bash
# Stop hook
if git diff --name-only HEAD | grep -qE '^backend/app/.*\.py$'; then
  graphify update . 2>&1 | head -20 || echo "[graphify] update failed (non-blocking)"
fi
```

## 10. Implementation Phases

The implementation plan (to be generated by the `writing-plans` skill) will follow this order. Phases are largely independent except where noted.

| # | Phase | Depends on |
|---|---|---|
| 0 | Commit this design doc to git | — |
| 1 | Create directory structure (`docs/{operations,architecture,features,roadmap,_archive}/`) | 0 |
| 2 | One-shot doc moves + symlink AGENTS.md | 1 |
| 3 | Split `TECHNICAL_SPEC.md` → `docs/architecture/*.md` (7 files) | 1 |
| 4 | Refactor `CLAUDE.md` (≈400 → ≈250 lines) | 2, 3 |
| 5 | Create the 3 slash commands in `.claude/commands/` | — |
| 6 | Generate graphify backend + add Stop hook | 4 |
| 7 | Write `docs/architecture/overview.md` with Mermaid | 3 |
| 8 | Write `docs/operations/commands.md` (audit of `scripts/` suspects) | 2 |
| 9 | Grep + sed pass: fix internal references broken by moves; final review | all |

**Effort estimate**: 4–6 hours (varies with how much I decide alone vs. checkpoint with the user).

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Bad split of `TECHNICAL_SPEC.md` (wrong topic boundaries) | Future doc churn | Phase 3 must read full doc before splitting; surface the split plan for user approval before applying |
| Broken internal links after moves | Doc rot | Phase 9 dedicated grep+sed pass; check all `*.md` references |
| Symlink `AGENTS.md` not portable | Low — single dev on macOS/Linux | Documented; if Windows ever appears, fall back to a stub file |
| `Stop` hook regression breaks session end | Annoyance | Best-effort wrapper; failure logs but does not propagate |
| Graphify produces noisy / unhelpful output | Low ROI on B-a | Manual review of first generation; if useless, drop the hook (not the rest of the spec) |

## 12. Out of Scope (deferred sub-projects, for traceability)

These were discussed during brainstorming and explicitly deferred:

- **Sub-project C** — Application code refactor (backend services, frontend components, technical debt). Should follow B (graph reveals targets).
- **Sub-project D** — Performance optimisations. Should follow B + C.
- **`scripts/` cleanup** — Identification of obsolete shell scripts (`backup.sh` vs `backup_postgres.sh`, `setup_auto_backup.sh` vs `setup_cron_backup.sh`, root `deploy.sh` / `deploy-prod.sh` / `update.sh` / `restart.sh` vs `scripts/deploy*.sh`). The audit list will be captured in `docs/operations/commands.md` during phase 8 of this spec, but no shell scripts will be deleted.
- **Frontend dependency graph** — can be added by re-running graphify on `frontend/src/` if useful later.
- **Infrastructure topology diagram** — a future ops/security sub-project.
- **Mermaid data-flow / sequence diagrams** — pipeline already documented textually; not adding more visuals unless a real need surfaces.
