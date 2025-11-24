#!/bin/bash

# Subscription Tracker - Restart Script
# Simple restart of all services without pulling changes or rebuilding

set -e  # Exit on error

echo "🔄 Restarting services..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found. Please run from project root."
    exit 1
fi

# Restart all services
echo -e "${BLUE}🔄 Restarting all containers...${NC}"
docker-compose restart
echo ""

# Wait for services
echo -e "${BLUE}⏳ Waiting for services...${NC}"
sleep 5

# Check health
echo -e "${BLUE}🏥 Checking service health...${NC}"
echo ""

BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
if [ "$BACKEND_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Backend: Healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend: Status $BACKEND_STATUS${NC}"
fi

FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 || echo "000")
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Frontend: Healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend: Status $FRONTEND_STATUS${NC}"
fi

echo ""
echo -e "${GREEN}✅ Restart complete!${NC}"

# Show container status
echo ""
echo -e "${BLUE}📊 Container Status:${NC}"
docker-compose ps
