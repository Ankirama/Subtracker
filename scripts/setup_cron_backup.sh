#!/bin/bash
#
# Setup System Cron for PostgreSQL Backups
# Installs cron job in /etc/cron.d/ (no user home directory required)
#
# Usage: sudo ./setup_cron_backup.sh [options]
# Options:
#   --uninstall    Remove the cron job
#   --status       Check if cron job is installed
#

set -e

# Configuration
CRON_FILE="/etc/cron.d/subscription-tracker-backup"
BACKUP_HOUR="${BACKUP_HOUR:-2}"           # Default: 2 AM
BACKUP_MINUTE="${BACKUP_MINUTE:-0}"       # Default: 0 minutes
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"  # Default: 14 days (2 weeks)

# Get project directory (parent of scripts/)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_SCRIPT="${PROJECT_DIR}/scripts/backup_postgres.sh"
BACKUP_DIR="${PROJECT_DIR}/backups"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${YELLOW}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run with sudo"
        echo "Usage: sudo $0"
        exit 1
    fi
}

show_status() {
    echo -e "${GREEN}=== Backup Cron Status ===${NC}"
    if [ -f "$CRON_FILE" ]; then
        print_success "Cron job is installed"
        echo ""
        echo "Configuration:"
        cat "$CRON_FILE"
        echo ""
        echo "Recent backups:"
        ls -lht "${BACKUP_DIR}"/postgres_backup_*.sql.gz 2>/dev/null | head -5 || echo "  No backups found"
        echo ""
        echo "Last log entries:"
        tail -10 "$LOG_FILE" 2>/dev/null || echo "  No log file found"
    else
        print_error "Cron job is NOT installed"
        echo "Run: sudo $0"
    fi
}

uninstall_cron() {
    check_root
    print_status "Removing backup cron job..."

    if [ -f "$CRON_FILE" ]; then
        rm -f "$CRON_FILE"
        print_success "Cron job removed: $CRON_FILE"
    else
        echo "Cron job was not installed"
    fi
}

install_cron() {
    check_root

    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}  PostgreSQL Backup Cron Setup${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""

    # Validate backup script exists
    if [ ! -f "$BACKUP_SCRIPT" ]; then
        print_error "Backup script not found: $BACKUP_SCRIPT"
        exit 1
    fi

    # Make backup script executable
    chmod +x "$BACKUP_SCRIPT"
    print_success "Backup script is executable"

    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    print_success "Backup directory exists: $BACKUP_DIR"

    # Create the cron file
    print_status "Installing cron job..."

    cat > "$CRON_FILE" << EOF
# Subscription Tracker - Automated PostgreSQL Backup
# Installed by: scripts/setup_cron_backup.sh
# Schedule: Daily at ${BACKUP_HOUR}:${BACKUP_MINUTE}
# Retention: ${RETENTION_DAYS} days

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Backup environment variables
BACKUP_DIR=${BACKUP_DIR}
POSTGRES_CONTAINER=subtracker_db
POSTGRES_DB=subscription_tracker
BACKUP_RETENTION_DAYS=${RETENTION_DAYS}

# Run backup daily
${BACKUP_MINUTE} ${BACKUP_HOUR} * * * root cd ${PROJECT_DIR} && ${BACKUP_SCRIPT} >> ${LOG_FILE} 2>&1
EOF

    # Set proper permissions (required for /etc/cron.d/)
    chmod 644 "$CRON_FILE"

    print_success "Cron job installed: $CRON_FILE"

    echo ""
    echo -e "${GREEN}=== Setup Complete ===${NC}"
    echo ""
    echo "Configuration:"
    echo "  Schedule:    Daily at ${BACKUP_HOUR}:$(printf '%02d' ${BACKUP_MINUTE})"
    echo "  Retention:   ${RETENTION_DAYS} days"
    echo "  Backup dir:  ${BACKUP_DIR}"
    echo "  Log file:    ${LOG_FILE}"
    echo ""
    echo "Commands:"
    echo "  Manual backup:  ${BACKUP_SCRIPT}"
    echo "  Check status:   sudo $0 --status"
    echo "  Uninstall:      sudo $0 --uninstall"
    echo ""
}

# Parse command line arguments
case "${1:-}" in
    --uninstall)
        uninstall_cron
        ;;
    --status)
        show_status
        ;;
    --help|-h)
        echo "Usage: sudo $0 [options]"
        echo ""
        echo "Options:"
        echo "  (none)       Install/update cron job"
        echo "  --status     Check cron job status"
        echo "  --uninstall  Remove cron job"
        echo "  --help       Show this help"
        echo ""
        echo "Environment variables:"
        echo "  BACKUP_HOUR            Hour to run backup (default: 2)"
        echo "  BACKUP_MINUTE          Minute to run backup (default: 0)"
        echo "  BACKUP_RETENTION_DAYS  Days to keep backups (default: 14)"
        ;;
    *)
        install_cron
        ;;
esac
