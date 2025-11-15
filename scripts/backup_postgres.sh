#!/bin/bash
#
# PostgreSQL Automated Backup Script
# Creates timestamped backups and manages retention
#

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTAINER_NAME="${POSTGRES_CONTAINER:-subscriptions_db}"
DATABASE="${POSTGRES_DB:-subscription_tracker}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/postgres_backup_${TIMESTAMP}.sql.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

echo -e "${GREEN}Starting PostgreSQL backup...${NC}"
echo "Database: ${DATABASE}"
echo "Container: ${CONTAINER_NAME}"
echo "Backup file: ${BACKUP_FILE}"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}Error: Container ${CONTAINER_NAME} is not running${NC}"
    exit 1
fi

# Create backup
echo -e "${YELLOW}Creating backup...${NC}"
docker exec -t "${CONTAINER_NAME}" pg_dump -U postgres -d "${DATABASE}" | gzip > "${BACKUP_FILE}"

# Check if backup was successful
if [ $? -eq 0 ] && [ -f "${BACKUP_FILE}" ]; then
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo -e "${GREEN}✓ Backup completed successfully${NC}"
    echo "Size: ${BACKUP_SIZE}"
else
    echo -e "${RED}✗ Backup failed${NC}"
    exit 1
fi

# Clean up old backups
echo -e "${YELLOW}Cleaning up old backups (keeping last ${RETENTION_DAYS} days)...${NC}"
find "${BACKUP_DIR}" -name "postgres_backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete

# Count remaining backups
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "postgres_backup_*.sql.gz" -type f | wc -l)
echo -e "${GREEN}✓ Cleanup completed${NC}"
echo "Total backups: ${BACKUP_COUNT}"

# List recent backups
echo ""
echo "Recent backups:"
ls -lh "${BACKUP_DIR}"/postgres_backup_*.sql.gz 2>/dev/null | tail -5 || echo "No backups found"

echo ""
echo -e "${GREEN}=== Backup Summary ===${NC}"
echo "Latest backup: ${BACKUP_FILE}"
echo "Retention: ${RETENTION_DAYS} days"
echo "Total backups: ${BACKUP_COUNT}"
