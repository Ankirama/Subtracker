#!/bin/bash
# ===========================================
# Subscription Tracker - Database Restore Script
# ===========================================

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env.production"
BACKUP_DIR="$PROJECT_DIR/backups"

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

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Subscription Tracker Restore${NC}"
echo -e "${GREEN}======================================${NC}"

# List available backups
echo ""
echo -e "${YELLOW}Available backups:${NC}"
ls -lh "$BACKUP_DIR"/subtracker_db_*.sql.gz 2>/dev/null || { echo "No backups found"; exit 1; }
echo ""

# Check if backup file was provided as argument
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: $0 <backup_file>${NC}"
    echo "Example: $0 subtracker_db_20241122_020000.sql.gz"
    echo ""
    echo "Or use the latest backup:"
    LATEST=$(ls -t "$BACKUP_DIR"/subtracker_db_*.sql.gz 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        echo "  $0 $(basename "$LATEST")"
    fi
    exit 1
fi

BACKUP_FILE="$BACKUP_DIR/$1"

if [ ! -f "$BACKUP_FILE" ]; then
    # Try with full path
    if [ -f "$1" ]; then
        BACKUP_FILE="$1"
    else
        echo -e "${RED}Error: Backup file not found: $1${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}>>> Preparing to restore from: $(basename "$BACKUP_FILE")${NC}"
echo ""
echo -e "${RED}WARNING: This will OVERWRITE the current database!${NC}"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Get the postgres container name
POSTGRES_CONTAINER=$(docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" ps -q postgres 2>/dev/null || echo "subtracker_postgres")

if [ -z "$POSTGRES_CONTAINER" ]; then
    echo -e "${RED}Error: PostgreSQL container not found${NC}"
    exit 1
fi

# Stop backend and celery to prevent connections
echo -e "${YELLOW}>>> Stopping application services...${NC}"
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" stop backend celery-worker celery-beat || true
echo -e "${GREEN}✓ Services stopped${NC}"

# Drop and recreate database
echo -e "${YELLOW}>>> Dropping existing database...${NC}"
docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB;"
echo -e "${GREEN}✓ Database recreated${NC}"

# Restore from backup
echo -e "${YELLOW}>>> Restoring database...${NC}"
gunzip -c "$BACKUP_FILE" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" "$POSTGRES_DB"
echo -e "${GREEN}✓ Database restored${NC}"

# Restart services
echo -e "${YELLOW}>>> Restarting application services...${NC}"
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" start backend celery-worker celery-beat
echo -e "${GREEN}✓ Services restarted${NC}"

# Wait and verify
sleep 5
echo ""
echo -e "${YELLOW}>>> Verifying restore...${NC}"

# Check backend health
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/health" | grep -q "200"; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${YELLOW}Warning: Backend health check failed - may need more time to start${NC}"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Restore Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
