#!/usr/bin/env bash
#
# Install the repo-managed git hooks into .git/hooks.
#
# Uses symlinks so the installed hook always tracks the latest version
# of the script in scripts/. Re-run any time the hook script changes
# (it doesn't change often; this is a one-shot for new clones).

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$REPO_ROOT/.git/hooks"
SCRIPT_DIR="$REPO_ROOT/scripts"

install_hook() {
  local name="$1"
  local source="$SCRIPT_DIR/$name.sh"
  local target="$HOOK_DIR/$name"

  if [[ ! -f "$source" ]]; then
    echo "ERROR: $source does not exist"
    exit 1
  fi

  chmod +x "$source"

  if [[ -e "$target" || -L "$target" ]]; then
    if [[ -L "$target" && "$(readlink "$target")" == "$source" ]]; then
      echo "[install-hooks] $name already installed -> $source"
      return 0
    fi
    echo "[install-hooks] Backing up existing $name to $name.backup"
    mv "$target" "$target.backup"
  fi

  ln -s "$source" "$target"
  echo "[install-hooks] Installed $name -> $source"
}

install_hook pre-commit

echo "[install-hooks] Done. Hooks installed in $HOOK_DIR"
