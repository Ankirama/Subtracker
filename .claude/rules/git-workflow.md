# Git workflow (MANDATORY)

## Branch policy
- **NEVER push directly to `main`.** Always create a feature branch and open a PR.
- Push to `main` only after explicit user validation with a stated reason.
- Branch naming: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`, `hotfix/<slug>`.
  Older branches use `feature/<slug>`; new ones follow the house `feat/` prefix.
- CI (`ci.yml`) runs on PRs to `main` / `develop` and on push to `main`.

## PR workflow
`ticket → branch → implement → lint/test → commit → push → PR → wait for approval`
(the global workflow in `~/.claude/CLAUDE.md`). Conventional Commits.

## Pre-commit checklist
A hook lives at `scripts/pre-commit.sh` — install once per clone with `./scripts/install-hooks.sh`.
It runs frontend lint + `tsc` when `frontend/` changes, and backend black + flake8 on staged
`backend/app/` files (via the dev container; skipped with a warning if the container is down).
Or run `/precommit` for the full checklist. CI additionally runs `ruff check` — see
`.claude/rules/conventions.md`.

Manual fallback:
- Backend: `docker compose -f docker-compose.dev.yml exec backend python -m black --check app/`
  and `... python -m flake8 app/ --max-line-length=120` (auto-fix: drop `--check`), plus
  `uvx ruff check backend`.
- Frontend: `npm --prefix frontend run lint`.

Commit only once linters pass (warnings OK, errors not).
