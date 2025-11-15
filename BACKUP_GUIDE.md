# PostgreSQL Backup & Restore Guide

Automated backup system for your subscription tracker database.

## Quick Start

### Setup Automated Backups

Run the setup script to configure automatic backups:

```bash
bash scripts/setup_auto_backup.sh
```

This will:
- Make scripts executable
- Let you choose backup schedule (daily, every 6h, every 12h, or custom)
- Configure retention policy (default: 7 days)
- Set up cron job for automatic backups
- Optionally create an initial backup

## Manual Operations

### Create Manual Backup

```bash
bash scripts/backup_postgres.sh
```

**Output:**
- Creates timestamped backup: `backups/postgres_backup_YYYYMMDD_HHMMSS.sql.gz`
- Automatically removes backups older than retention period
- Shows backup size and summary

### Restore from Backup

```bash
bash scripts/restore_postgres.sh backups/postgres_backup_20251115_140530.sql.gz
```

**Safety Features:**
- Creates safety backup before restore
- Requires confirmation (`yes` to proceed)
- Validates container is running
- Provides rollback option if restore fails

### List Available Backups

```bash
ls -lh backups/
```

## Configuration

### Backup Settings

Configuration is stored in `.backup_env` (created by setup script):

```bash
BACKUP_DIR="./backups"
POSTGRES_CONTAINER="subscriptions_postgres"
POSTGRES_DB="subscriptions"
BACKUP_RETENTION_DAYS=7
```

### Customize Settings

Edit `.backup_env` to change:
- `BACKUP_DIR`: Where backups are stored
- `BACKUP_RETENTION_DAYS`: How long to keep backups

### Schedule Options

**Daily at 2 AM:**
```
0 2 * * *
```

**Every 6 hours:**
```
0 */6 * * *
```

**Every 12 hours:**
```
0 */12 * * *
```

**Custom schedule:**
Use cron format: `minute hour day month weekday`

## Monitoring

### View Backup Logs

```bash
tail -f backups/backup.log
```

### Check Cron Job

```bash
crontab -l
```

### Check Last Backup

```bash
ls -lth backups/ | head -5
```

## Troubleshooting

### Container Not Running

**Error:** `Container subscriptions_postgres is not running`

**Solution:**
```bash
docker-compose -f docker-compose.dev.yml up -d postgres
```

### Permission Denied

**Error:** Permission issues with backup files

**Solution:**
```bash
chmod +x scripts/*.sh
sudo chown -R $USER backups/
```

### Disk Space Full

**Error:** No space left on device

**Solution:**
1. Check disk space: `df -h`
2. Reduce retention days in `.backup_env`
3. Manually remove old backups: `rm backups/postgres_backup_20251001_*.sql.gz`

### Restore Failed

If restore fails:
1. Check the safety backup was created
2. Restore from safety backup: `bash scripts/restore_postgres.sh backups/pre_restore_backup_*.sql.gz`
3. Check container logs: `docker logs subscriptions_postgres`

## Best Practices

### Retention Policy

- **Development:** 7 days (default)
- **Staging:** 14 days
- **Production:** 30+ days

### Backup Schedule

- **Low traffic:** Daily at off-peak hours
- **Medium traffic:** Every 12 hours
- **High traffic:** Every 6 hours

### Off-site Backups

For production, also copy backups to cloud storage:

```bash
# Example: sync to AWS S3
aws s3 sync backups/ s3://your-bucket/subscription-tracker-backups/

# Example: sync to Google Drive (with rclone)
rclone sync backups/ gdrive:subscription-tracker-backups/
```

### Test Restores

Regularly test your backup restoration process:

```bash
# 1. Create test backup
bash scripts/backup_postgres.sh

# 2. Note latest backup file
LATEST=$(ls -t backups/postgres_backup_*.sql.gz | head -1)

# 3. Test restore (creates safety backup automatically)
bash scripts/restore_postgres.sh "$LATEST"
```

## Advanced Usage

### Backup to External Directory

```bash
BACKUP_DIR=/mnt/external/backups bash scripts/backup_postgres.sh
```

### Custom Retention

```bash
BACKUP_RETENTION_DAYS=30 bash scripts/backup_postgres.sh
```

### Backup Specific Database

```bash
POSTGRES_DB=custom_db bash scripts/backup_postgres.sh
```

### Compressed vs Uncompressed

Current backups are gzipped. To create uncompressed backup:

```bash
# Edit backup_postgres.sh, change:
docker exec -t "${CONTAINER_NAME}" pg_dump -U postgres -d "${DATABASE}" > "${BACKUP_FILE%.gz}"
```

## Migration Use Cases

### Move to New Server

1. **On old server:**
```bash
bash scripts/backup_postgres.sh
scp backups/postgres_backup_*.sql.gz newserver:/path/to/project/backups/
```

2. **On new server:**
```bash
bash scripts/restore_postgres.sh backups/postgres_backup_*.sql.gz
```

### Restore to Different Database

```bash
# Edit restore script temporarily or create custom restore:
gunzip -c backups/postgres_backup_*.sql.gz | \
  docker exec -i subscriptions_postgres psql -U postgres -d different_db
```

### Copy Database

Create a copy of the database:

```bash
# 1. Backup
bash scripts/backup_postgres.sh

# 2. Create new database
docker exec -i subscriptions_postgres psql -U postgres -c "CREATE DATABASE subscriptions_copy;"

# 3. Restore to new database
POSTGRES_DB=subscriptions_copy bash scripts/restore_postgres.sh backups/postgres_backup_*.sql.gz
```

## Security

### Backup File Permissions

Backups contain sensitive data. Ensure proper permissions:

```bash
chmod 600 backups/*.sql.gz
```

### Encrypted Backups

For sensitive data, encrypt backups:

```bash
# After creating backup
gpg --symmetric --cipher-algo AES256 backups/postgres_backup_*.sql.gz

# To restore encrypted backup
gpg --decrypt backups/postgres_backup_*.sql.gz.gpg | \
  docker exec -i subscriptions_postgres psql -U postgres -d subscriptions
```

### Exclude from Git

Backups are automatically excluded via `.gitignore`:
```
backups/
.backup_env
backup.log
*.sql.gz
```

## Files Overview

```
scripts/
├── backup_postgres.sh       # Create backup
├── restore_postgres.sh      # Restore from backup
└── setup_auto_backup.sh     # Setup automation

backups/                     # Backup storage (created automatically)
├── postgres_backup_*.sql.gz # Timestamped backups
├── backup.log              # Backup execution logs
└── pre_restore_backup_*.sql.gz # Safety backups before restore

.backup_env                  # Backup configuration (created by setup)
```

## Support

For issues or questions:
1. Check this guide
2. Review logs: `tail -f backups/backup.log`
3. Check Docker logs: `docker logs subscriptions_postgres`
4. Verify container status: `docker ps`
