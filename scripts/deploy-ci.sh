#!/bin/bash
# ===========================================
# CI/CD Automated Deployment Script
# ===========================================
# This script is optimized for automated deployment via GitHub Actions
# For manual deployment, use deploy.sh instead

set -e  # Exit on error
set -o pipefail  # Fail on pipe errors

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-$PROJECT_DIR/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Error handler
handle_error() {
    log_error "Deployment failed at line $1"
    log_warning "Rolling back changes..."
    rollback_deployment
    exit 1
}

trap 'handle_error $LINENO' ERR

# Rollback function
rollback_deployment() {
    log_warning "Attempting to rollback to previous state..."

    # Find latest backup
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR" | grep -E '^[0-9]{8}_[0-9]{6}$' | head -1)

    if [ -n "$LATEST_BACKUP" ]; then
        log_info "Found backup: $LATEST_BACKUP"

        # Restore docker-compose config if exists
        if [ -f "$BACKUP_DIR/$LATEST_BACKUP/docker-compose-backup.yml" ]; then
            cp "$BACKUP_DIR/$LATEST_BACKUP/docker-compose-backup.yml" "$COMPOSE_FILE"
            log_success "Restored docker-compose configuration"
        fi

        # Restart with previous configuration
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

        log_success "Rollback completed"
    else
        log_warning "No backup found for rollback"
    fi
}

# Main deployment process
main() {
    log_info "Starting CI/CD deployment..."

    # Pre-deployment checks
    log_info "Running pre-deployment checks..."

    # Check Docker is running
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running"
        exit 1
    fi
    log_success "Docker is running"

    # Check environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env.production file not found at $ENV_FILE"
        exit 1
    fi
    log_success "Environment file found"

    # Create necessary directories
    log_info "Creating required directories..."
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$PROJECT_DIR/logs"
    log_success "Directories created"

    # Create backup of current state
    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    CURRENT_BACKUP_DIR="$BACKUP_DIR/$BACKUP_TIMESTAMP"
    mkdir -p "$CURRENT_BACKUP_DIR"

    log_info "Creating backup at $CURRENT_BACKUP_DIR..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config > "$CURRENT_BACKUP_DIR/docker-compose-backup.yml" 2>/dev/null || true

    # Export current database if containers are running
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "postgres.*Up"; then
        log_info "Backing up database..."
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres pg_dump -U "${POSTGRES_USER:-subscriptions}" "${POSTGRES_DB:-subscriptions}" > "$CURRENT_BACKUP_DIR/database-backup.sql" 2>/dev/null || log_warning "Database backup failed (may not be running)"
    fi
    log_success "Backup created"

    # Pull latest code
    log_info "Pulling latest code..."
    cd "$PROJECT_DIR"
    git fetch origin
    git reset --hard origin/main
    log_success "Code updated"

    # Login to GitHub Container Registry if credentials provided
    if [ -n "$GHCR_TOKEN" ] && [ -n "$GHCR_USERNAME" ]; then
        log_info "Logging into GitHub Container Registry..."
        echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
        log_success "Logged into GHCR"
    fi

    # Pull latest images
    log_info "Pulling latest Docker images..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull
    log_success "Images pulled"

    # Stop services gracefully
    log_info "Stopping services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans
    log_success "Services stopped"

    # Start services with new images
    log_info "Starting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    log_success "Services started"

    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 15

    # Run database migrations
    log_info "Running database migrations..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend alembic upgrade head
    log_success "Migrations completed"

    # Health checks
    log_info "Running health checks..."
    sleep 5

    # Check backend health (internal)
    MAX_ATTEMPTS=12
    ATTEMPT=1
    while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
        log_info "Health check attempt $ATTEMPT/$MAX_ATTEMPTS..."

        HEALTH_STATUS=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")

        if [ "$HEALTH_STATUS" = "200" ]; then
            log_success "Backend is healthy (status: $HEALTH_STATUS)"
            break
        fi

        if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
            log_error "Backend health check failed after $MAX_ATTEMPTS attempts (status: $HEALTH_STATUS)"
            log_info "Backend logs:"
            docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs --tail=50 backend
            exit 1
        fi

        log_warning "Backend not ready yet (status: $HEALTH_STATUS), waiting..."
        sleep 5
        ATTEMPT=$((ATTEMPT + 1))
    done

    # Check all services are running
    log_info "Checking service status..."
    SERVICES_STATUS=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps)

    if ! echo "$SERVICES_STATUS" | grep -E "(Up|running)" > /dev/null; then
        log_error "Some services are not running properly"
        echo "$SERVICES_STATUS"
        exit 1
    fi
    log_success "All services are running"

    # Cleanup old images
    log_info "Cleaning up old Docker images..."
    docker image prune -f --filter "until=168h" || log_warning "Image cleanup failed (non-critical)"

    # Cleanup old backups (keep last 10)
    log_info "Cleaning up old backups..."
    cd "$BACKUP_DIR"
    ls -t | grep -E '^[0-9]{8}_[0-9]{6}$' | tail -n +11 | xargs -r rm -rf || log_warning "Backup cleanup failed (non-critical)"

    log_success "Deployment completed successfully!"

    # Display deployment info
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}  Deployment Complete!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo "Backup created at: $CURRENT_BACKUP_DIR"
    echo ""
    echo "Service status:"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    echo ""
}

# Run main deployment
main

exit 0
