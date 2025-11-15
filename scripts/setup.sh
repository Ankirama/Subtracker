#!/bin/bash

# Subscription Tracker - Setup Script
# This script helps you set up the development environment

set -e

echo "🚀 Subscription Tracker - Setup Script"
echo "========================================"
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "✅ .env file already exists"
    read -p "Do you want to regenerate keys? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping key generation. Using existing .env file."
        exit 0
    fi
fi

# Copy .env.example if .env doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
fi

# Generate JWT secret
echo "🔑 Generating JWT secret key..."
JWT_SECRET=$(openssl rand -hex 32)

# Generate encryption key
echo "🔐 Generating encryption key..."
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Update .env file
echo "📝 Updating .env file..."

# For macOS and Linux compatibility
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env
    sed -i '' "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env
else
    # Linux
    sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env
    sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env
fi

echo ""
echo "✅ Keys generated successfully!"
echo ""
echo "⚠️  IMPORTANT: Add your OpenAI API key to .env:"
echo "   OPENAI_API_KEY=sk-your-key-here"
echo ""
echo "Next steps:"
echo "1. Add your OPENAI_API_KEY to .env"
echo "2. Run: docker-compose -f docker-compose.dev.yml up -d"
echo "3. Run: docker-compose exec backend alembic upgrade head"
echo "4. Visit: http://localhost:5173"
echo ""
echo "For more details, see SETUP.md"
