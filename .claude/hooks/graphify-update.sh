#!/usr/bin/env bash
# .claude/hooks/graphify-update.sh
# Stop hook: refresh graphify if backend Python files changed this session.
# Best-effort: failure must NOT break session end.

set -uo pipefail   # NB: no `-e` — we tolerate non-fatal errors.

# The Stop hook fires with the user's shell cwd, which may be a subdirectory
# (e.g. frontend/). Anchor everything to the script's own project root so that
# `git status backend/app` and `graphify update .` operate on the right tree.
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 0

# Detect changes to backend/app/**/*.py since the last commit OR in the working tree.
# We use `git status --porcelain` because the hook runs at session end, possibly
# before the user has committed.
changed=$(git status --porcelain backend/app 2>/dev/null | grep -E '\.py$' || true)

# Also include staged + committed-this-session changes vs origin/main.
upstream_diff=$(git diff --name-only origin/main...HEAD 2>/dev/null | grep -E '^backend/app/.*\.py$' || true)

if [ -z "$changed" ] && [ -z "$upstream_diff" ]; then
    # No backend changes; nothing to update.
    exit 0
fi

# Try the update. Cap output at 20 lines to avoid noise.
if command -v graphify >/dev/null 2>&1; then
    graphify update . 2>&1 | head -20 || \
        echo "[graphify-update.sh] graphify update failed (non-blocking)"
else
    echo "[graphify-update.sh] graphify CLI not in PATH (non-blocking)"
fi

exit 0
