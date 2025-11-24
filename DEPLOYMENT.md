# Deployment Guide

This guide explains how to deploy updates to your Subscription Tracker application.

## Quick Reference

| Script | Use Case | What It Does |
|--------|----------|--------------|
| `./deploy.sh` | Full deployment with dependency changes | Pull → Rebuild → Restart → Health Check |
| `./update.sh` | Quick code updates (no dependency changes) | Pull → Copy files → Restart → Health Check |
| `./restart.sh` | Simple restart (no changes) | Restart all containers → Health Check |

## Deployment Scenarios

### 1. Full Deployment (New Dependencies or Major Changes)

Use this when:
- Dependencies changed (requirements.txt, package.json)
- Docker configuration changed
- First-time deployment
- After major updates

```bash
./deploy.sh
```

**What happens:**
1. Pulls latest code from Git (main branch)
2. Stops all containers
3. Rebuilds containers from scratch
4. Starts all services
5. Checks health status

**Time:** ~2-5 minutes (depending on rebuild)

---

### 2. Quick Update (Code Changes Only)

Use this when:
- Only Python/TypeScript code changed
- No new dependencies
- Quick bug fixes or feature updates

```bash
./update.sh
```

**What happens:**
1. Pulls latest code from Git
2. Copies updated Python files to running containers
3. Restarts backend and Celery (frontend auto-reloads)
4. Checks health status

**Time:** ~10-15 seconds

**Note:** Frontend uses Vite hot-reload, so changes appear automatically without restart.

---

### 3. Simple Restart

Use this when:
- Services are misbehaving
- Need to clear state
- No code changes needed

```bash
./restart.sh
```

**What happens:**
1. Restarts all containers
2. Waits for services to be ready
3. Checks health status

**Time:** ~5-10 seconds

---

## Manual Deployment

If you prefer manual control, here's what each script does:

### Full Deployment (Manual)
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check health
curl http://localhost:8000/health
curl http://localhost:5173
```

### Quick Update (Manual)
```bash
# Pull latest changes
git pull origin main

# Copy files to containers
docker cp backend/app/. subscriptions_backend:/app/app/
docker cp backend/app/. subscriptions_celery:/app/app/

# Restart services
docker-compose restart backend celery

# Check health
curl http://localhost:8000/health
```

---

## Checking Service Status

After any deployment, you can check:

```bash
# Container status
docker-compose ps

# Backend health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:5173

# View logs
docker-compose logs -f backend
docker-compose logs -f celery
docker-compose logs -f frontend
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
docker-compose logs backend
docker-compose logs celery

# Try a full rebuild
./deploy.sh
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Restart database
docker-compose restart postgres

# Check database logs
docker-compose logs postgres
```

### Port Already in Use

```bash
# Find what's using the port
lsof -i :8000  # Backend
lsof -i :5173  # Frontend
lsof -i :5432  # PostgreSQL

# Stop the conflicting process or change ports in docker-compose.yml
```

### Celery Tasks Not Running

```bash
# Check Celery status
docker-compose logs celery

# Restart Celery
docker-compose restart celery

# Check Redis connection
docker-compose logs redis
```

---

## Production Deployment Checklist

Before deploying to production:

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Backups created
- [ ] SSL certificates configured
- [ ] Firewall rules set
- [ ] Monitoring enabled
- [ ] Error tracking configured

---

## Environment Variables

Key environment variables to configure:

```env
# Backend
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# OAuth (if using Gmail)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Email (if using email notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email
SMTP_PASSWORD=your-password
```

---

## Best Practices

1. **Always test in development first**
   - Test changes locally before deploying
   - Run tests: `docker exec subscriptions_backend pytest`

2. **Use appropriate script**
   - Code-only changes → `./update.sh` (fast)
   - Dependency changes → `./deploy.sh` (full rebuild)
   - Just restarting → `./restart.sh` (quick)

3. **Monitor after deployment**
   - Check logs: `docker-compose logs -f`
   - Test critical features
   - Monitor error rates

4. **Keep backups**
   - Database backups before major deployments
   - Git tags for releases: `git tag v1.0.0`

5. **Rollback plan**
   - Keep previous version tagged
   - Know how to revert: `git checkout v1.0.0`
   - Database rollback scripts ready

---

## Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs [service]`
2. Verify container status: `docker-compose ps`
3. Check documentation in project README
4. Review error messages carefully

For specific services:
- Backend API: http://localhost:8000/docs
- Database: Use your database client
- Redis: Use Redis CLI or GUI tool
