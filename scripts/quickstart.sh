#!/bin/bash

# Subscription Tracker - Quick Start Script
# This script runs the complete setup and starts the application

set -e

echo "🚀 Subscription Tracker - Quick Start"
echo "====================================="
echo ""

# Run setup
./scripts/setup.sh

# Check if OPENAI_API_KEY is set
if grep -q "OPENAI_API_KEY=sk-" .env; then
    echo ""
    echo "✅ OpenAI API key detected"
else
    echo ""
    echo "⚠️  OpenAI API key not found in .env"
    echo "Please add your key before continuing:"
    echo "   OPENAI_API_KEY=sk-your-key-here"
    echo ""
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start Docker Compose
echo ""
echo "🐳 Starting Docker services..."
docker-compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "🔍 Checking service health..."
docker-compose ps

# Run database migrations
echo ""
echo "📊 Running database migrations..."
docker-compose exec backend alembic upgrade head

# Test backend health
echo ""
echo "🏥 Testing backend health..."
sleep 3
curl -s http://localhost:8000/health | python3 -m json.tool || echo "Backend not ready yet, give it a few more seconds"

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Application URLs:"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8000/docs"
echo "   Backend Health: http://localhost:8000/health"
echo ""
echo "📊 Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   Stop services: docker-compose stop"
echo "   Restart services: docker-compose restart"
echo ""
echo "📚 Documentation:"
echo "   Setup guide: SETUP.md"
echo "   Development guide: CLAUDE.md"
echo "   Technical spec: TECHNICAL_SPEC.md"
