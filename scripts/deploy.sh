#!/bin/bash
# ===========================================
# Subscription Tracker - Production Deployment Script
# ===========================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env.production"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Subscription Tracker Deployment${NC}"
echo -e "${GREEN}======================================${NC}"

# Check if .env.production exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: .env.production file not found!${NC}"
    echo "Please copy .env.production.example to .env.production and configure it."
    exit 1
fi

# Load environment variables
source "$ENV_FILE"

# Function to print status
print_status() {
    echo -e "${YELLOW}>>> $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Pre-deployment checks
print_status "Running pre-deployment checks..."

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi
print_success "Docker is running"

# Check required environment variables
required_vars=("POSTGRES_PASSWORD" "JWT_SECRET_KEY" "ENCRYPTION_KEY" "OPENAI_API_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" == "CHANGE_ME"* ]; then
        echo -e "${RED}Error: $var is not properly set in .env.production${NC}"
        exit 1
    fi
done
print_success "Environment variables configured"

# Create necessary directories
print_status "Creating required directories..."
mkdir -p "$PROJECT_DIR/backups"
mkdir -p "$PROJECT_DIR/logs"
print_success "Directories created"

# Check if proxy network exists (required for Traefik integration)
print_status "Checking Traefik proxy network..."
if ! docker network ls | grep -q "proxy"; then
    echo -e "${RED}Error: 'proxy' network not found. Make sure Traefik is running.${NC}"
    echo "Create it with: docker network create proxy"
    exit 1
fi
print_success "Traefik proxy network found"

# Pull latest images or build
print_status "Building Docker images..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache
print_success "Images built successfully"

# Stop existing containers (if any)
print_status "Stopping existing containers..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans || true
print_success "Existing containers stopped"

# Start services
print_status "Starting services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
print_success "Services started"

# Wait for services to be healthy
print_status "Waiting for services to be healthy..."
sleep 10

# Check service health
services=("postgres" "redis" "backend" "celery_worker" "celery_beat" "frontend")
for service in "${services[@]}"; do
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps | grep -q "$service.*Up"; then
        print_success "$service is running"
    else
        echo -e "${RED}Warning: $service may not be running properly${NC}"
    fi
done

# Run database migrations
print_status "Running database migrations..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend alembic upgrade head
print_success "Migrations completed"

# Setup automated backups
print_status "Setting up automated database backups..."
if [ -f "$PROJECT_DIR/scripts/setup_cron_backup.sh" ]; then
    chmod +x "$PROJECT_DIR/scripts/setup_cron_backup.sh"
    # Run with sudo if available, otherwise warn
    if sudo -n true 2>/dev/null; then
        sudo BACKUP_RETENTION_DAYS=14 "$PROJECT_DIR/scripts/setup_cron_backup.sh"
        print_success "Automated backups configured (daily at 2 AM, 14 days retention)"
    else
        echo -e "${YELLOW}Warning: Cannot setup cron without sudo${NC}"
        echo "Run manually: sudo BACKUP_RETENTION_DAYS=14 $PROJECT_DIR/scripts/setup_cron_backup.sh"
    fi
else
    echo -e "${YELLOW}Warning: Backup setup script not found${NC}"
fi

# Final health check
print_status "Running final health check..."
sleep 5

# Check if backend is responding (via Traefik)
FULL_DOMAIN="${SUBDOMAIN}.${DOMAIN_NAME}"
if curl -s -o /dev/null -w "%{http_code}" "https://${FULL_DOMAIN}/health" | grep -q "200"; then
    print_success "Backend health check passed (via Traefik)"
else
    # Fallback to direct container check
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/health" | grep -q "200"; then
        print_success "Backend health check passed (direct)"
    else
        echo -e "${YELLOW}Warning: Backend health check failed - service may need more time to start${NC}"
    fi
fi

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Your application should be available at: https://${FULL_DOMAIN}"
echo ""
echo "Note: SSL is handled by Traefik automatically."
echo ""
echo "Useful commands:"
echo "  View logs:     docker compose -f $COMPOSE_FILE logs -f"
echo "  Stop services: docker compose -f $COMPOSE_FILE down"
echo "  Restart:       docker compose -f $COMPOSE_FILE restart"
echo ""
echo "Backup commands:"
echo "  Manual backup: $PROJECT_DIR/scripts/backup_postgres.sh"
echo "  Backup status: sudo $PROJECT_DIR/scripts/setup_cron_backup.sh --status"
echo "  List backups:  ls -lh $PROJECT_DIR/backups/"
echo ""
