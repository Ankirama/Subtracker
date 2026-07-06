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

## Shell Scripts Inventory (as of 2026-04-25)

### Root-level

| Script | Purpose | Status |
|---|---|---|
| `deploy-prod.sh` | Pulls pre-built images from GHCR and deploys to production; accepts optional `IMAGE_TAG` (default: `latest`) | `suspect` |
| `deploy.sh` | Full deployment — pulls latest git changes, rebuilds containers, restarts services; accepts `dev\|prod` (default: `prod`) | `suspect` |
| `restart.sh` | Restarts all services without pulling changes or rebuilding; accepts `dev\|prod` (default: `prod`) | `active` |
| `update.sh` | Quick update — pulls latest git changes and restarts services without rebuilding; for code-only changes; accepts `dev\|prod` (default: `prod`) | `active` |

### `scripts/`

| Script | Purpose | Status |
|---|---|---|
| `backup.sh` | Full database backup with retention management; designed for daily cron execution; reads `.env.production` | `suspect` |
| `backup_postgres.sh` | PostgreSQL automated backup — creates timestamped `.sql.gz` backups and manages retention via `BACKUP_RETENTION_DAYS` | `suspect` |
| `create_admin.sh` | Creates an admin user in the application database; usage: `create_admin.sh <email> <password> [name]` | `active` |
| `deploy-ci.sh` | Automated deployment script optimised for GitHub Actions CI/CD; not intended for manual use (use `deploy.sh` instead) | `suspect` |
| `deploy.sh` | Production deployment script — project-relative counterpart to the root `deploy.sh`; pulls and restarts services | `suspect` |
| `install_sudoers.sh` | Installs sudoers configuration so the deploy user can run backup scripts without a password; requires `sudo` | `active` |
| `quickstart.sh` | One-step setup + start: delegates to `scripts/setup.sh` then starts the application | `suspect` |
| `restore.sh` | Database restore from a backup file using project `.env.production`; counterpart to `backup.sh` | `suspect` |
| `restore_postgres.sh` | PostgreSQL restore script — restores the database from a given backup file via the running container | `suspect` |
| `setup.sh` | Interactive development-environment setup: generates `.env`, encryption keys, and starts Docker services | `suspect` |
| `setup_auto_backup.sh` | Configures a cron job for daily automated PostgreSQL backups (user-crontab approach) | `suspect` |
| `setup_cron_backup.sh` | Installs a system-wide cron job in `/etc/cron.d/` for PostgreSQL backups; supports `--uninstall` and `--status`; requires `sudo` | `suspect` |
| `sync_custom_period.sh` | Triggers an email sync over a custom time period with configurable rate limiting | `active` |

## Suspected Duplicates / Cleanup Candidates

The following pairs/triples warrant review (cleanup is OUT OF SCOPE for this refactor — captured here for a future sub-project):

- `scripts/backup.sh` vs `scripts/backup_postgres.sh` — wrapper, or two parallel implementations?
- `scripts/restore.sh` vs `scripts/restore_postgres.sh` — same question.
- `scripts/setup_auto_backup.sh` vs `scripts/setup_cron_backup.sh` — likely overlap.
- Root `deploy.sh` vs `scripts/deploy.sh` vs `scripts/deploy-ci.sh` vs root `deploy-prod.sh` — multiple deploy entry-points; document which is canonical.
- `scripts/setup.sh` vs `scripts/quickstart.sh` — likely overlap with `docs/setup.md`.

## Ad-Hoc Commands Not Covered Elsewhere

### Migrations
```bash
# Roll back the most recent migration
docker-compose exec backend alembic downgrade -1
```

### Installing dependencies
```bash
# Backend: install then pin in backend/requirements.txt, and restart the container
docker-compose exec backend pip install <package>
docker-compose -f docker-compose.dev.yml restart backend

# Frontend
docker-compose exec frontend npm install <package>
```
