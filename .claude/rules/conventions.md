# Project conventions

> Generic conventions (Conventional Commits, type hints, thin views, tests required,
> comments explain *why*) are inherited from `~/.claude/CLAUDE.md`. This file records only
> the **project-specific overrides** for the FastAPI + React/Chakra stack.

## Stack overrides (vs global defaults)
- **Backend is FastAPI**, not Django: thin route handlers in `app/api/`, business logic in
  `app/services/`, SQLAlchemy 2.0 models in `app/models/`, Pydantic v2 for validation.
- **Format & lint with black + flake8**, not ruff:
  `python -m black app/` and `python -m flake8 app/ --max-line-length=120` (run in the
  backend container — see `.claude/rules/git-workflow.md`).
- **Frontend is Chakra UI**, not Tailwind: function components + hooks, TypeScript `strict`,
  ESLint + Prettier clean, no inline styles. Wrap the app in Chakra's `ThemeProvider`.
- **Tests**: backend `pytest` (via `docker-compose exec backend pytest`); frontend Vitest +
  React Testing Library. Tests required for new logic.

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
Canonical run: `docker-compose exec backend pytest` (compose provides the test env). A
host-local `uv run pytest` only works if you first build a venv from `backend/requirements.txt`.
Never inline `DATABASE_URL=...` / other env prefixes — they defeat permission allow rules and
force prompts. For host-local runs, put machine-local test env in `.claude/settings.local.json`
`env` (gitignored).
