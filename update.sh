#!/bin/bash

# Subscription Tracker - Quick Update Script
# This script pulls latest changes and restarts services WITHOUT rebuilding
# Use this when only code changes (no dependency changes)

set -e  # Exit on error

echo "⚡ Quick update starting..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found. Please run from project root."
    exit 1
fi

# Step 1: Pull latest changes
echo -e "${BLUE}📥 Pulling latest changes from Git...${NC}"
git pull origin main
echo ""

# Step 2: Copy updated files to containers (if they're running)
echo -e "${BLUE}📋 Copying updated files to containers...${NC}"

# Copy backend files
if docker ps | grep -q subscriptions_backend; then
    echo "  → Updating backend files..."
    docker cp backend/app/. subscriptions_backend:/app/app/
fi

# Copy Celery files (same backend code)
if docker ps | grep -q subscriptions_celery; then
    echo "  → Updating Celery files..."
    docker cp backend/app/. subscriptions_celery:/app/app/
fi

echo ""

# Step 3: Restart services
echo -e "${BLUE}🔄 Restarting services...${NC}"
docker-compose restart backend celery
echo ""

# Step 4: Wait for services
echo -e "${BLUE}⏳ Waiting for services to restart...${NC}"
sleep 5

# Step 5: Check health
echo -e "${BLUE}🏥 Checking service health...${NC}"
echo ""

BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
if [ "$BACKEND_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Backend: Healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend: Status $BACKEND_STATUS${NC}"
fi

echo ""
echo -e "${GREEN}✅ Update complete!${NC}"
echo ""
echo "💡 Note: Frontend updates are automatic (Vite hot-reload)"
echo "💡 If dependencies changed, run ./deploy.sh instead"
