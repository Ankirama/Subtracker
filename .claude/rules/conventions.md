# Project conventions

> Generic conventions (Conventional Commits, type hints, thin views, tests required,
> comments explain *why*) are inherited from `~/.claude/CLAUDE.md`. This file records only
> the **project-specific overrides** for the FastAPI + React/Chakra stack.

## Stack overrides (vs global defaults)
- **Backend is FastAPI**, not Django: thin route handlers in `app/api/`, business logic in
  `app/services/`, SQLAlchemy 2.0 models in `app/models/`, Pydantic v2 for validation.
- **Backend lint is black + ruff in CI, black + flake8 in the pre-commit hook** (checked
  2026-10-06). CI (`.github/workflows/ci.yml`) runs `black --check .` and `ruff check .`
  in `backend/` (config `backend/ruff.toml`); `scripts/pre-commit.sh` runs black + `flake8
  --max-line-length=120` in the dev container. Code must pass **both** ruff and flake8 until
  the hook is aligned with CI (follow-up). ruff is not in `requirements.txt`.
- **Frontend is Chakra UI**, not Tailwind: function components + hooks, TypeScript `strict`,
  ESLint clean (CI also runs `tsc --noEmit --strict`), no inline styles. Prettier is **not**
  a dependency — don't assume a formatter on the frontend.
- **Tests**: backend `pytest` in `backend/tests/`; frontend Vitest + React Testing Library +
  MSW, tests co-located as `*.test.ts(x)`, shared helpers in `frontend/src/test/`. Tests
  required for new logic. **Backend tests are disabled in CI** ("temporarily", see the
  commented step in `ci.yml`) — run them locally before a PR; frontend tests do run in CI.

## Broad exception handling (backend)
`except Exception` / bare `except:` is allowed **only** with a reason annotation:
```python
except Exception as e:  # noqa: BLE001 — short reason a narrow catch isn't possible
    ...
```
Legitimate reasons: best-effort startup/shutdown, fail-open infra (Redis/cache),
middleware fall-through, 3rd-party libs with undocumented exceptions, loggers in error paths.
Otherwise use a specific exception type. Grep `backend/` for existing `# noqa: BLE001` examples.

## Language policy
All committed artefacts are **English** (code, comments, docstrings, error/log messages,
tests, docs, commit/PR text, diagram labels). Conversational French is fine; never ship a
mixed-language file — translate inline before committing.

## API & database conventions
- All endpoints prefixed `/api/`, RESTful naming; errors as `{"detail": ...}`; list endpoints
  paginate via `page` + `page_size`.
- UUID primary keys; `created_at` / `updated_at` on most tables; soft delete via `is_active`
  where applicable; JSONB for flexible/structured metadata.
- **Always filter by `user_id`** for multi-tenancy (see `.claude/rules/security.md`).

## Testing config (avoid env-prefix prompts)
Canonical run: `docker compose -f docker-compose.dev.yml exec backend pytest` (compose
provides the test env; there is no default compose file, so `-f` is required). A
host-local `uv run pytest` only works if you first build a venv from `backend/requirements.txt`.
Never inline `DATABASE_URL=...` / other env prefixes — they defeat permission allow rules and
force prompts. For host-local runs, put machine-local test env in `.claude/settings.local.json`
`env` (gitignored).
