# CI & Image Build Pipeline

How GitHub Actions validates changes and publishes container images for
Subscription Tracker. Actual deployment happens on the NAS via Dockhand —
see [deploy-nas-dockhand.md](deploy-nas-dockhand.md).

## Overview

Three workflows run in GitHub Actions:

1. **CI** (`.github/workflows/ci.yml`) — quality & security checks on PRs and on `main`.
2. **Build & Publish Images** (`.github/workflows/cd.yml`) — builds the backend/frontend
   Docker images and pushes them to the GitHub Container Registry (GHCR) on every push to `main`.
3. **Security Scan** (`.github/workflows/security-scan.yml`) — scheduled weekly security scans.

There is no automated server deploy. The NAS pulls the published GHCR images
when you redeploy the stack from Dockhand.

## CI Workflow (`ci.yml`)

**Triggers:**
- Pull requests to `main` / `develop`
- Pushes to `main`

**Jobs (run in parallel):**
- **Backend Quality & Security** — Black (format check), Ruff (lint), mypy (type check),
  `pip-audit` (dependency vulnerabilities). Backed by ephemeral Postgres + Redis service
  containers. Uses the `test` GitHub environment for its secrets.
- **Frontend Quality & Security** — ESLint, `tsc --noEmit --strict`, Vitest unit tests,
  production build, `npm audit`. Uploads the `frontend/dist` build artifact.
- **Database Migration Validation** — runs `alembic branches` (conflict check),
  `alembic upgrade head`, then a downgrade/upgrade round-trip against a throwaway Postgres.
- **Secrets Detection** — Gitleaks scan over full git history.
- **Security Summary** — aggregates the results and fails if any required check failed.

> Backend `pytest` and Strix are currently commented out in the workflow (see the inline
> notes in `ci.yml`). Run tests locally with `docker compose exec backend pytest`.

### CI secrets

CI reads a few secrets (JWT/encryption/API keys, Gitleaks license) from the repository and
from the `test` GitHub environment. Set them under
**Settings → Secrets and variables → Actions** and **Settings → Environments → test**.
These are throwaway/test values, not production credentials.

## Build & Publish Images (`cd.yml`)

**Triggers:**
- Push to `main`
- Manual (`workflow_dispatch`)

**What it does (job `build`):**
- Logs in to GHCR with the built-in `GITHUB_TOKEN` (needs `packages: write`).
- Builds the backend image from `./backend` and the frontend image from `./frontend`
  with Buildx, using a registry-backed layer cache.
- Pushes both images to GHCR:
  - `ghcr.io/<owner>/<repo>-backend`
  - `ghcr.io/<owner>/<repo>-frontend`
- Tags each image with the branch name, `<branch>-<sha>`, and `latest` on the default branch.

No extra secrets are required — `GITHUB_TOKEN` is provided automatically.

### Image visibility

GHCR packages default to **private**. To let the NAS pull them either make the
`*-backend` / `*-frontend` packages public, or add GHCR credentials in Dockhand.
Both options are covered in [deploy-nas-dockhand.md](deploy-nas-dockhand.md#step-1--make-the-ghcr-images-pullable).

## Security Scan (`security-scan.yml`)

**Triggers:**
- Schedule: weekly
- Manual (`workflow_dispatch`)

Runs dependency and image vulnerability scanning, code security analysis, and secrets
detection, producing security reports.

## Deploying

The images published by `cd.yml` are consumed by the NAS/Dockhand stack. To roll a new
build onto the NAS: Dockhand → stack `subtracker` → **Pull** → **Redeploy**. The one-shot
`migrate` service runs `alembic upgrade head` on each deploy. Full instructions, including
first-time setup and automatic PostgreSQL backups, are in
[deploy-nas-dockhand.md](deploy-nas-dockhand.md).

## Hardening notes

Recommended repository settings for a lean, safe pipeline:

- **Branch protection** on `main`: require PR review, require CI status checks to pass,
  require branches to be up to date.
- **Workflow permissions**: keep the default minimal token; `cd.yml` only requests
  `contents: read` + `packages: write`.
- **Secret hygiene**: no secrets in code or logs; rotate CI/API tokens periodically;
  keep test secrets separate from any production values (which now live only in the
  NAS stack's Dockhand Environment, never in this repo).

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Alembic Migrations Guide](https://alembic.sqlalchemy.org/)
- [Gitleaks Secrets Detection](https://github.com/gitleaks/gitleaks)
