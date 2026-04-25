# Setup Guide - Subscription Tracker

Quick start guide to get the Subscription Tracker running locally.

## Prerequisites

- **Docker** and **Docker Compose** installed
- **OpenAI API key** (get one at https://platform.openai.com/)
- (Optional) **Fastmail account** or JMAP-compatible email for testing

## Initial Setup (5 minutes)

### 1. Clone and Navigate
```bash
# Already done if you're reading this!
cd subscription_tracker
```

### 2. Configure Environment Variables
```bash
# Copy the example environment file
cp .env.example .env

# Open .env and configure the following:
```

**Required Configuration in `.env`:**

```bash
# 1. Generate JWT Secret (run this command):
openssl rand -hex 32
# Add the output to JWT_SECRET_KEY in .env

# 2. Generate Encryption Key (run this command):
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add the output to ENCRYPTION_KEY in .env

# 3. Add your OpenAI API Key
OPENAI_API_KEY=sk-your-key-here
```

**Quick Setup Script:**
```bash
# Run this to generate both keys at once
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
echo "ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

### 3. Start the Application
```bash
# Start all services (this will take a few minutes the first time)
docker-compose -f docker-compose.dev.yml up -d

# Watch the logs to see progress
docker-compose -f docker-compose.dev.yml logs -f
```

**Expected Output:**
```
✅ postgres - healthy
✅ redis - healthy
✅ backend - starting
✅ celery_worker - starting
✅ frontend - starting
```

### 4. Initialize Database
```bash
# Wait for backend to be ready (check logs), then run migrations
docker-compose exec backend alembic upgrade head

# You should see:
# INFO  [alembic.runtime.migration] Running upgrade  -> xxxxx, initial migration
```

### 5. Verify Installation
```bash
# Check all services are running
docker-compose ps

# Test backend health
curl http://localhost:8000/health
# Expected: {"status":"healthy","app":"Subscription Tracker","version":"0.1.0"}

# Test frontend
curl http://localhost:5173
# Expected: HTML response

# Access the application:
# Frontend: http://localhost:5173
# Backend API Docs: http://localhost:8000/docs
```

## Troubleshooting

### Port Conflicts
If you see "port already in use" errors:
```bash
# Check what's using the ports
lsof -i :5173  # Frontend
lsof -i :8000  # Backend
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis

# Stop conflicting services or change ports in docker-compose.dev.yml
```

### Services Won't Start
```bash
# Stop everything and start fresh
docker-compose -f docker-compose.dev.yml down

# Remove volumes (⚠️ deletes data)
docker-compose -f docker-compose.dev.yml down -v

# Start again
docker-compose -f docker-compose.dev.yml up -d
```

### Backend Connection Failed
```bash
# Check backend logs
docker-compose logs backend

# Common issues:
# - Missing OPENAI_API_KEY in .env
# - Missing JWT_SECRET_KEY or ENCRYPTION_KEY
# - Database not ready (wait 10 seconds and try again)
```

### Database Migration Errors
```bash
# Check migration status
docker-compose exec backend alembic current

# If no migrations, run upgrade
docker-compose exec backend alembic upgrade head

# If multiple heads (conflict), see CLAUDE.md troubleshooting section
```

## Quick Reference Commands

### Daily Development
```bash
# Start services
docker-compose -f docker-compose.dev.yml up -d

# Stop services (keeps data)
docker-compose -f docker-compose.dev.yml stop

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f celery_worker

# Restart a service
docker-compose restart backend
```

### Database Operations
```bash
# Access database
docker-compose exec postgres psql -U postgres -d subscription_tracker

# Create migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Apply migration
docker-compose exec backend alembic upgrade head

# Rollback migration
docker-compose exec backend alembic downgrade -1
```

### Testing
```bash
# Backend tests
docker-compose exec backend pytest

# Frontend tests
docker-compose exec frontend npm test
```

## What's Next?

After setup is complete, you can:

1. **Access the application**:
   - Frontend: http://localhost:5173
   - API Documentation: http://localhost:8000/docs

2. **Test the setup**:
   - Click "Test Backend Connection" button in the frontend
   - Explore the API at http://localhost:8000/docs

3. **Start development**:
   - Backend code in `backend/app/`
   - Frontend code in `frontend/src/`
   - Changes auto-reload (hot-reload enabled)

4. **Review documentation**:
   - Architecture: [`docs/architecture/overview.md`](architecture/overview.md)
   - Development guide: `CLAUDE.md`
   - API reference: http://localhost:8000/docs

## Current Status

✅ **Completed**:
- Project structure created
- Docker Compose configuration
- Backend foundation (FastAPI)
- Frontend foundation (React + TypeScript)
- Database setup (PostgreSQL + Alembic)
- Celery workers configured
- Hot-reload enabled for development

⏳ **Pending** (Week 1-2):
- Authentication endpoints (register, login, JWT)
- Email provider interface (JMAP)
- OpenAI integration for email analysis
- Subscription CRUD endpoints
- Dashboard UI components

## Support

- **Documentation**: See [`docs/architecture/overview.md`](architecture/overview.md) and `CLAUDE.md`
- **Logs**: `docker-compose logs -f <service-name>`
- **Reset**: `docker-compose down -v && docker-compose up -d`

---

**Setup complete!** 🎉 You're ready to start developing.
