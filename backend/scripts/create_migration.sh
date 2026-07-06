#!/bin/bash

# Script to create initial database migration
# This creates the migration file based on the models

echo "📊 Creating initial database migration..."

docker compose exec backend alembic revision --autogenerate -m "Initial migration - create users table"

echo "✅ Migration created!"
echo ""
echo "To apply the migration, run:"
echo "docker compose exec backend alembic upgrade head"
