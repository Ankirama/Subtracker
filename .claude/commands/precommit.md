---
description: Run the full pre-commit checklist (lint, format, suggest commit message)
---

# /precommit

Run the project's mandatory pre-commit workflow defined in CLAUDE.md.

## Steps

1. **Show current state**
   - Run `git status` and `git diff --staged` (or `git diff` if nothing is staged yet) to surface what is about to be committed.
   - If there are no changes, stop here and report "Nothing to commit".

2. **Backend formatter (black)**
   - Run: `docker-compose -f docker-compose.dev.yml exec -T backend python -m black --check app/`
   - If it fails, run `docker-compose -f docker-compose.dev.yml exec -T backend python -m black app/` to auto-fix, then re-run the check.

3. **Backend linter (flake8)**
   - Run: `docker-compose -f docker-compose.dev.yml exec -T backend python -m flake8 app/ --max-line-length=120`
   - Errors block; warnings are tolerated. Surface both clearly.

4. **Frontend linter**
   - Run: `cd frontend && npm run lint`
   - Surface failures; do not auto-fix without asking.

5. **Decide**
   - If all gates pass: read the staged diff, then propose a commit message following the conventional-commits-ish style used in `git log` (look at the last 5 commits via `git log --oneline -5`). Format the suggestion as a HEREDOC the user can copy. Do NOT commit yourself.
   - If any gate fails: list the violations grouped by tool and stop. Do not propose a commit message.

## Notes

- Use `-T` with `docker-compose exec` so it works in non-interactive mode.
- If the backend container is not running, surface a clear error and suggest `docker-compose -f docker-compose.dev.yml up -d`.
- Never `git add` files yourself — the user controls staging.
