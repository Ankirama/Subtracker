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
  # Only lint staged Python files inside backend/app/, not the whole tree.
  # The repo has many pre-existing E501 lines; checking the full tree would
  # block every commit. We rely on the user's CI / periodic sweeps for that.
  local backend_files
  backend_files=$(echo "$CHANGED_FILES" | grep -E '^backend/app/.*\.py$' || true)
  if [[ -z "$backend_files" ]]; then
    return 0
  fi
  if ! docker compose -f docker-compose.dev.yml ps --status running backend 2>/dev/null | grep -q backend; then
    echo "[pre-commit] WARN: backend container not running; skipping backend lint."
    echo "[pre-commit]       Start it with 'docker compose -f docker-compose.dev.yml up -d backend' to enable this check."
    return 0
  fi
  # Strip the leading 'backend/' so paths are relative to the container's WORKDIR.
  local container_paths
  container_paths=$(echo "$backend_files" | sed 's|^backend/||' | tr '\n' ' ')
  echo "[pre-commit] Backend black + flake8 on staged files..."
  # shellcheck disable=SC2086 — intentional word-splitting on the file list
  docker compose -f docker-compose.dev.yml exec -T backend python -m black --check $container_paths
  # shellcheck disable=SC2086
  docker compose -f docker-compose.dev.yml exec -T backend python -m flake8 --max-line-length=120 $container_paths
}

run_frontend_checks
run_backend_checks

echo "[pre-commit] OK"
