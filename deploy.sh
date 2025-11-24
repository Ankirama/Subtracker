#!/bin/bash

# Subscription Tracker - Full Deployment Script
# This script pulls latest changes, rebuilds containers, and restarts services

set -e  # Exit on error

echo "🚀 Starting deployment..."
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

# Step 2: Stop containers
echo -e "${BLUE}🛑 Stopping containers...${NC}"
docker-compose down
echo ""

# Step 3: Rebuild containers (in case dependencies changed)
echo -e "${BLUE}🔨 Rebuilding containers...${NC}"
docker-compose build --no-cache
echo ""

# Step 4: Start containers
echo -e "${BLUE}🚀 Starting containers...${NC}"
docker-compose up -d
echo ""

# Step 5: Wait for services to be ready
echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"
sleep 10

# Step 6: Check service health
echo -e "${BLUE}🏥 Checking service health...${NC}"
echo ""

# Check backend
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
if [ "$BACKEND_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Backend: Healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend: Status $BACKEND_STATUS${NC}"
fi

# Check frontend
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 || echo "000")
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Frontend: Healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend: Status $FRONTEND_STATUS${NC}"
fi

# Check container status
echo ""
echo -e "${BLUE}📊 Container Status:${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "🌐 Access your application:"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   Docs:     http://localhost:8000/docs"
