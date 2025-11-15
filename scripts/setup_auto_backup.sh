#!/bin/bash
#
# Setup Automated PostgreSQL Backups
# Configures cron job for daily backups
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_SCRIPT="${PROJECT_DIR}/scripts/backup_postgres.sh"

echo -e "${GREEN}PostgreSQL Auto-Backup Setup${NC}"
echo "Project directory: ${PROJECT_DIR}"
echo ""

# Make scripts executable
chmod +x "${PROJECT_DIR}/scripts/backup_postgres.sh"
chmod +x "${PROJECT_DIR}/scripts/restore_postgres.sh"
echo -e "${GREEN}✓ Scripts made executable${NC}"

# Configuration options
echo ""
echo "Backup Schedule Options:"
echo "1) Daily at 2 AM"
echo "2) Every 6 hours"
echo "3) Every 12 hours"
echo "4) Custom (you specify)"
read -p "Choose schedule (1-4): " SCHEDULE_CHOICE

case ${SCHEDULE_CHOICE} in
    1)
        CRON_SCHEDULE="0 2 * * *"
        DESCRIPTION="Daily at 2 AM"
        ;;
    2)
        CRON_SCHEDULE="0 */6 * * *"
        DESCRIPTION="Every 6 hours"
        ;;
    3)
        CRON_SCHEDULE="0 */12 * * *"
        DESCRIPTION="Every 12 hours"
        ;;
    4)
        echo ""
        echo "Enter cron schedule (e.g., '0 2 * * *' for daily at 2 AM):"
        read -p "Schedule: " CRON_SCHEDULE
        DESCRIPTION="Custom: ${CRON_SCHEDULE}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Backup retention
echo ""
read -p "Backup retention in days [7]: " RETENTION_DAYS
RETENTION_DAYS=${RETENTION_DAYS:-7}

# Create environment file for backup settings
ENV_FILE="${PROJECT_DIR}/.backup_env"
cat > "${ENV_FILE}" <<EOF
# Backup configuration
BACKUP_DIR="${PROJECT_DIR}/backups"
POSTGRES_CONTAINER="subscriptions_db"
POSTGRES_DB="subscription_tracker"
BACKUP_RETENTION_DAYS=${RETENTION_DAYS}
EOF

echo -e "${GREEN}✓ Configuration saved to ${ENV_FILE}${NC}"

# Create cron job
CRON_COMMAND="cd ${PROJECT_DIR} && source ${ENV_FILE} && ${BACKUP_SCRIPT} >> ${PROJECT_DIR}/backups/backup.log 2>&1"
CRON_ENTRY="${CRON_SCHEDULE} ${CRON_COMMAND}"

echo ""
echo -e "${YELLOW}Setting up cron job...${NC}"
echo "Schedule: ${DESCRIPTION}"
echo "Command: ${CRON_COMMAND}"
echo ""

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -v "${BACKUP_SCRIPT}") | crontab - 2>/dev/null || true

# Add new cron job
(crontab -l 2>/dev/null; echo "${CRON_ENTRY}") | crontab -

echo -e "${GREEN}✓ Cron job installed${NC}"

# Create initial backup
echo ""
read -p "Create initial backup now? (yes/no): " CREATE_BACKUP
if [ "${CREATE_BACKUP}" = "yes" ]; then
    echo -e "${YELLOW}Creating initial backup...${NC}"
    source "${ENV_FILE}"
    bash "${BACKUP_SCRIPT}"
fi

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Backup schedule: ${DESCRIPTION}"
echo "Retention: ${RETENTION_DAYS} days"
echo "Backup directory: ${PROJECT_DIR}/backups"
echo "Log file: ${PROJECT_DIR}/backups/backup.log"
echo ""
echo "Useful commands:"
echo "  List backups:  ls -lh ${PROJECT_DIR}/backups/"
echo "  Manual backup: bash ${BACKUP_SCRIPT}"
echo "  Restore:       bash ${PROJECT_DIR}/scripts/restore_postgres.sh <backup_file>"
echo "  View logs:     tail -f ${PROJECT_DIR}/backups/backup.log"
echo "  List cron:     crontab -l"
echo "  Remove cron:   crontab -e  (then delete the backup line)"
