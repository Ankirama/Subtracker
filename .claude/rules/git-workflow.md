# Git workflow (MANDATORY)

## Branch policy
- **NEVER push directly to `main`.** Always create a feature branch and open a PR.
- Push to `main` only after explicit user validation with a stated reason.
- Branch naming: `feature/<slug>`, `fix/<slug>`, `hotfix/<slug>`.

## PR workflow
`ticket → branch → implement → lint/test → commit → push → PR → wait for approval`.
Use `/ticket` to open the issue, `/commit` for Conventional Commits, `/pr [issue#]` for the PR.

## Pre-commit checklist
A hook lives at `scripts/pre-commit.sh` — install once per clone with `./scripts/install-hooks.sh`.
It runs frontend lint + `tsc` when `frontend/` changes, and backend black + flake8 (via the dev
container) when `backend/` changes. Or run `/precommit` for the full checklist.

Manual fallback:
- Backend: `docker compose -f docker-compose.dev.yml exec backend python -m black --check app/`
  and `... python -m flake8 app/ --max-line-length=120` (auto-fix: drop `--check`).
- Frontend: `npm run lint` in `frontend/`.

Commit only once linters pass (warnings OK, errors not).
