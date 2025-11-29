#!/bin/bash

# Subscription Tracker - Production Deployment Script (Hybrid Approach)
# This script pulls pre-built images from GHCR and deploys to production
# Usage: ./deploy-prod.sh [IMAGE_TAG]
# Default IMAGE_TAG: latest

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
IMAGE_TAG=${1:-latest}
GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-ankirama/subtracker}
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
ENV_FILE=".env.production"

echo -e "${BLUE}🚀 Starting Production Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Repository: $GITHUB_REPOSITORY"
echo "Image Tag:  $IMAGE_TAG"
echo ""

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}📋 Loading environment from $ENV_FILE...${NC}"
    set -a  # Automatically export all variables
    source "$ENV_FILE"
    set +a
    echo -e "${GREEN}✓ Environment loaded${NC}"
    echo ""
else
    echo -e "${RED}❌ Error: $ENV_FILE not found${NC}"
    echo "Please create $ENV_FILE with required variables"
    exit 1
fi

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}❌ Error: $COMPOSE_FILE not found${NC}"
    exit 1
fi

# Step 1: Create backup
echo -e "${BLUE}💾 Creating backup...${NC}"
mkdir -p "$BACKUP_DIR"
if docker compose -f "$COMPOSE_FILE" ps > /dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" config > "$BACKUP_DIR/docker-compose-backup.yml" || true
    echo -e "${GREEN}✓ Backup created: $BACKUP_DIR${NC}"
else
    echo -e "${YELLOW}⚠ No running containers to backup${NC}"
fi
echo ""

# Step 2: Pull latest code (optional - for config files)
echo -e "${BLUE}📥 Pulling latest configuration...${NC}"
if [ -d ".git" ]; then
    # Stash deploy-prod.sh if it exists to preserve it
    if [ -f "deploy-prod.sh" ]; then
        cp deploy-prod.sh /tmp/deploy-prod.sh.backup
    fi

    git fetch origin main
    git reset --hard origin/main

    # Restore deploy-prod.sh if it was backed up and doesn't exist after pull
    if [ -f "/tmp/deploy-prod.sh.backup" ] && [ ! -f "deploy-prod.sh" ]; then
        cp /tmp/deploy-prod.sh.backup deploy-prod.sh
        chmod +x deploy-prod.sh
        echo -e "${YELLOW}⚠ Restored deploy-prod.sh (not in main branch yet)${NC}"
    fi

    echo -e "${GREEN}✓ Code updated${NC}"
else
    echo -e "${YELLOW}⚠ Not a git repository, skipping git pull${NC}"
fi
echo ""

# Step 3: Login to GitHub Container Registry
echo -e "${BLUE}🔐 Logging into GitHub Container Registry...${NC}"
if [ -n "$GHCR_TOKEN" ]; then
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
    echo -e "${GREEN}✓ Logged in to GHCR${NC}"
else
    echo -e "${YELLOW}⚠ GHCR_TOKEN not set, assuming already logged in${NC}"
fi
echo ""

# Step 4: Pull latest images
echo -e "${BLUE}📥 Pulling Docker images...${NC}"
export GITHUB_REPOSITORY IMAGE_TAG
docker compose -f "$COMPOSE_FILE" pull
echo -e "${GREEN}✓ Images pulled${NC}"
echo ""

# Step 5: Stop services
echo -e "${BLUE}🛑 Stopping services...${NC}"
docker compose -f "$COMPOSE_FILE" down
echo -e "${GREEN}✓ Services stopped${NC}"
echo ""

# Step 6: Start services with new images
echo -e "${BLUE}🚀 Starting services...${NC}"
docker compose -f "$COMPOSE_FILE" up -d
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Step 7: Wait for services to be ready
echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"
sleep 15
echo ""

# Step 8: Run database migrations
echo -e "${BLUE}🔄 Running database migrations...${NC}"
if docker compose -f "$COMPOSE_FILE" exec -T backend alembic upgrade head; then
    echo -e "${GREEN}✓ Migrations completed${NC}"
else
    echo -e "${RED}❌ Migration failed!${NC}"
    echo -e "${YELLOW}📋 Checking logs...${NC}"
    docker compose -f "$COMPOSE_FILE" logs --tail=50 backend
    exit 1
fi
echo ""

# Step 9: Health checks
echo -e "${BLUE}🏥 Running health checks...${NC}"
sleep 5

# Check backend health
BACKEND_HEALTHY=false
for i in {1..5}; do
    BACKEND_STATUS=$(docker compose -f "$COMPOSE_FILE" exec -T backend curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    if [ "$BACKEND_STATUS" = "200" ]; then
        BACKEND_HEALTHY=true
        break
    fi
    echo -e "${YELLOW}⏳ Attempt $i/5: Backend status $BACKEND_STATUS, retrying...${NC}"
    sleep 3
done

if [ "$BACKEND_HEALTHY" = true ]; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${RED}❌ Backend health check failed (status: $BACKEND_STATUS)${NC}"
    echo -e "${YELLOW}📋 Backend logs:${NC}"
    docker compose -f "$COMPOSE_FILE" logs --tail=100 backend
    echo ""
    echo -e "${RED}Deployment failed - rolling back...${NC}"

    # Rollback
    if [ -f "$BACKUP_DIR/docker-compose-backup.yml" ]; then
        cp "$BACKUP_DIR/docker-compose-backup.yml" "$COMPOSE_FILE"
        docker compose -f "$COMPOSE_FILE" down
        docker compose -f "$COMPOSE_FILE" up -d
        echo -e "${YELLOW}✓ Rolled back to previous version${NC}"
    fi
    exit 1
fi

# Check all services are running
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
docker compose -f "$COMPOSE_FILE" ps
echo ""

UNHEALTHY=$(docker compose -f "$COMPOSE_FILE" ps --format json | grep -v '"State":"running"' || true)
if [ -n "$UNHEALTHY" ]; then
    echo -e "${RED}❌ Some services are not running properly${NC}"
    exit 1
fi

# Step 10: Cleanup
echo -e "${BLUE}🧹 Cleaning up old Docker images...${NC}"
docker image prune -f --filter "until=168h" || true
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Success!
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Deployment Successful!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "🌐 Your application is now running"
echo "📊 Monitor with: docker compose -f $COMPOSE_FILE logs -f"
echo "🔍 Check status: docker compose -f $COMPOSE_FILE ps"
echo ""
