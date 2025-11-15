#!/bin/bash
#
# PostgreSQL Restore Script
# Restores database from a backup file
#

set -e

# Configuration
CONTAINER_NAME="${POSTGRES_CONTAINER:-subscriptions_db}"
DATABASE="${POSTGRES_DB:-subscription_tracker}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: Backup file required${NC}"
    echo ""
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh ./backups/postgres_backup_*.sql.gz 2>/dev/null || echo "No backups found in ./backups/"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}Error: Backup file not found: ${BACKUP_FILE}${NC}"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}Error: Container ${CONTAINER_NAME} is not running${NC}"
    exit 1
fi

echo -e "${YELLOW}WARNING: This will restore the database from backup${NC}"
echo "Database: ${DATABASE}"
echo "Backup file: ${BACKUP_FILE}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

# Create a safety backup before restore
SAFETY_BACKUP="./backups/pre_restore_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
echo -e "${YELLOW}Creating safety backup first...${NC}"
docker exec -t "${CONTAINER_NAME}" pg_dump -U postgres -d "${DATABASE}" | gzip > "${SAFETY_BACKUP}"
echo -e "${GREEN}✓ Safety backup created: ${SAFETY_BACKUP}${NC}"

# Restore from backup
echo -e "${YELLOW}Restoring database...${NC}"
gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U postgres -d "${DATABASE}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database restored successfully${NC}"
    echo ""
    echo "Safety backup available at: ${SAFETY_BACKUP}"
else
    echo -e "${RED}✗ Restore failed${NC}"
    echo "You can restore the safety backup if needed:"
    echo "  $0 ${SAFETY_BACKUP}"
    exit 1
fi
