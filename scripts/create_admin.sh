#!/bin/bash
#
# Create an admin user for Subscription Tracker (local dev).
#
# Usage:
#   ./scripts/create_admin.sh admin@example.com yourpassword
#   ./scripts/create_admin.sh admin@example.com yourpassword "Admin Name"
#
# For the NAS/Dockhand deployment, exec into the backend container instead and run:
#   python -m scripts.create_admin --email <email> --password <password> [--name <name>]
# (see docs/operations/deploy-nas-dockhand.md).

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

COMPOSE_FILE="docker-compose.dev.yml"

if [ ! -f "$COMPOSE_FILE" ] || ! docker compose -f "$COMPOSE_FILE" ps --quiet backend 2>/dev/null | grep -q .; then
    echo "No running backend container found for $COMPOSE_FILE."
    echo ""
    echo "Start the dev stack first:"
    echo "  docker compose -f $COMPOSE_FILE up -d"
    exit 1
fi

echo "Creating admin user via $COMPOSE_FILE..."
if [ -n "$NAME" ]; then
    docker compose -f "$COMPOSE_FILE" exec -T backend \
        python -m scripts.create_admin --email "$EMAIL" --password "$PASSWORD" --name "$NAME"
else
    docker compose -f "$COMPOSE_FILE" exec -T backend \
        python -m scripts.create_admin --email "$EMAIL" --password "$PASSWORD"
fi
