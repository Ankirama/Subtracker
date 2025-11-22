#!/bin/bash
#
# Create an admin user for Subscription Tracker
#
# Usage:
#   ./scripts/create_admin.sh admin@example.com yourpassword
#   ./scripts/create_admin.sh admin@example.com yourpassword "Admin Name"
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <email> <password> [display_name]"
    echo ""
    echo "Examples:"
    echo "  $0 admin@example.com mypassword123"
    echo "  $0 admin@example.com mypassword123 'Admin User'"
    exit 1
fi

EMAIL="$1"
PASSWORD="$2"
NAME="${3:-}"

# Check if running in production (docker) or development
if [ -f "docker-compose.prod.yml" ] && docker compose -f docker-compose.prod.yml ps --quiet backend 2>/dev/null | grep -q .; then
    echo "Running in production mode (Docker)..."
    if [ -n "$NAME" ]; then
        docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \
            python -m scripts.create_admin --email "$EMAIL" --password "$PASSWORD" --name "$NAME"
    else
        docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \
            python -m scripts.create_admin --email "$EMAIL" --password "$PASSWORD"
    fi
elif [ -f "docker-compose.yml" ] && docker compose ps --quiet backend 2>/dev/null | grep -q .; then
    echo "Running in development mode (Docker)..."
    if [ -n "$NAME" ]; then
        docker compose exec -T backend python -m scripts.create_admin --email "$EMAIL" --password "$PASSWORD" --name "$NAME"
    else
        docker compose exec -T backend python -m scripts.create_admin --email "$EMAIL" --password "$PASSWORD"
    fi
else
    echo "No running Docker containers found."
    echo ""
    echo "Please start the services first:"
    echo "  Production: docker compose -f docker-compose.prod.yml --env-file .env.production up -d"
    echo "  Development: docker compose up -d"
    exit 1
fi
