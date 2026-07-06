# Commands & Scripts Reference

> Ad-hoc operational commands and an audit of `scripts/`. For day-to-day
> commands, see `CLAUDE.md` "Daily Commands". For workflows, see
> `.claude/commands/` (slash commands).

## Useful SQL Queries

```sql
-- Subscriptions pending review
SELECT * FROM email_processing_records
WHERE processing_status = 'pending_review'
  AND user_id = 'user-uuid'
ORDER BY processed_at DESC;

-- User spending summary by category
SELECT category, SUM(amount) AS total, COUNT(*) AS count
FROM subscriptions
WHERE user_id = 'user-uuid' AND is_active = TRUE
GROUP BY category;

-- Failed processing jobs
SELECT * FROM processing_jobs
WHERE status = 'failed'
ORDER BY created_at DESC;
```

## Shell Scripts Inventory

Deployment and server backup scripts were removed when deployment moved to the
NAS/Dockhand stack (see [deploy-nas-dockhand.md](deploy-nas-dockhand.md), which also
covers automatic PostgreSQL backups). The remaining scripts all support local
development or one-off admin tasks.

### `scripts/`

| Script | Purpose | Status |
|---|---|---|
| `setup.sh` | Interactive development-environment setup: generates `.env`, encryption keys, and starts Docker services | `active` |
| `quickstart.sh` | One-step setup + start: delegates to `scripts/setup.sh` then starts the application | `active` |
| `create_admin.sh` | Creates an admin user in the application database; usage: `create_admin.sh <email> <password> [name]` | `active` |
| `install-hooks.sh` | Installs the repo's git hooks (pre-commit lint/format) into `.git/hooks` | `active` |
| `pre-commit.sh` | Pre-commit hook body: runs frontend lint + tsc and backend black + flake8 on changed files | `active` |
| `sync_custom_period.sh` | Triggers an email sync over a custom time period with configurable rate limiting | `active` |

## Cleanup Candidates

The following overlap warrants review (cleanup is OUT OF SCOPE for this refactor —
captured here for a future sub-project):

- `scripts/setup.sh` vs `scripts/quickstart.sh` — likely overlap with `docs/setup.md`.

## Ad-Hoc Commands Not Covered Elsewhere

### Migrations
```bash
# Roll back the most recent migration
docker compose exec backend alembic downgrade -1
```

### Installing dependencies
```bash
# Backend: install then pin in backend/requirements.txt, and restart the container
docker compose exec backend pip install <package>
docker compose -f docker-compose.dev.yml restart backend

# Frontend
docker compose exec frontend npm install <package>
```
