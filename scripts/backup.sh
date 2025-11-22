#!/bin/bash
# ===========================================
# Subscription Tracker - Database Backup Script
# ===========================================
# Recommended: Run via cron daily
# Example crontab entry:
# 0 2 * * * /path/to/subscription_tracker/scripts/backup.sh >> /var/log/subtracker-backup.log 2>&1

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env.production"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS=7

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo -e "${RED}Error: .env.production not found${NC}"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Timestamp for backup files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/subtracker_db_$TIMESTAMP.sql.gz"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Subscription Tracker Backup${NC}"
echo -e "${GREEN}======================================${NC}"
echo "Timestamp: $(date)"
echo ""

# Perform database backup
echo -e "${YELLOW}>>> Creating database backup...${NC}"

# Get the postgres container name
POSTGRES_CONTAINER=$(docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" ps -q postgres 2>/dev/null || echo "subtracker_postgres")

if [ -z "$POSTGRES_CONTAINER" ]; then
    echo -e "${RED}Error: PostgreSQL container not found${NC}"
    exit 1
fi

# Dump database and compress
docker exec "$POSTGRES_CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✓ Backup created: $BACKUP_FILE ($BACKUP_SIZE)${NC}"
else
    echo -e "${RED}Error: Backup file was not created${NC}"
    exit 1
fi

# Clean up old backups
echo -e "${YELLOW}>>> Cleaning up old backups (older than $RETENTION_DAYS days)...${NC}"
DELETED_COUNT=$(find "$BACKUP_DIR" -name "subtracker_db_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo -e "${GREEN}✓ Deleted $DELETED_COUNT old backup(s)${NC}"

# List current backups
echo ""
echo -e "${YELLOW}Current backups:${NC}"
ls -lh "$BACKUP_DIR"/subtracker_db_*.sql.gz 2>/dev/null || echo "No backups found"

# Disk space check
echo ""
echo -e "${YELLOW}Backup disk usage:${NC}"
du -sh "$BACKUP_DIR"

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Backup Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
