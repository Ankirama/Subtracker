#!/usr/bin/env bash
#
# Subscription Tracker pre-commit hook.
#
# Runs the cheap, always-available frontend checks first and tries the
# backend Docker checks if the dev compose stack is up. Backend checks
# are skipped (with a warning) when Docker is unavailable so the hook
# never blocks committers who edit only frontend code without bringing
# the backend container up.
#
# Install via: scripts/install-hooks.sh

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

if [[ -z "$CHANGED_FILES" ]]; then
  exit 0
fi

run_frontend_checks() {
  if ! echo "$CHANGED_FILES" | grep -qE '^frontend/'; then
    return 0
  fi
  echo "[pre-commit] Frontend lint + tsc..."
  (
    cd frontend
    npm run lint
    npx tsc --noEmit
  )
}

run_backend_checks() {
  if ! echo "$CHANGED_FILES" | grep -qE '^backend/'; then
    return 0
  fi
  if ! docker compose -f docker-compose.dev.yml ps --status running backend 2>/dev/null | grep -q backend; then
    echo "[pre-commit] WARN: backend container not running; skipping backend lint."
    echo "[pre-commit]       Start it with 'docker compose -f docker-compose.dev.yml up -d backend' to enable this check."
    return 0
  fi
  echo "[pre-commit] Backend black + flake8..."
  docker compose -f docker-compose.dev.yml exec -T backend python -m black --check app/
  docker compose -f docker-compose.dev.yml exec -T backend python -m flake8 app/ --max-line-length=120
}

run_frontend_checks
run_backend_checks

echo "[pre-commit] OK"
