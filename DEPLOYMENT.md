# Subscription Tracker - Deployment Guide

Complete deployment guide for the Subscription Tracker application using the hybrid CI/CD approach.

## Quick Start

1. **Configure GitHub Secrets** (see "GitHub Repository Secrets" section)
2. **Set up production server** with Docker + Traefik
3. **Merge to main branch** → Automatic deployment starts
4. **Monitor deployment** in GitHub Actions

## Architecture Overview

```
GitHub CI (Build/Test) → GHCR (Images) → Production Server (Deploy)
```

**Deployment Flow:**
- CI: Tests code, builds Docker images
- CD: Pushes images to GitHub Container Registry
- Server: Pulls pre-built images and deploys

## Required Secrets

Configure in `Settings → Secrets and variables → Actions`:

```bash
SSH_HOST=192.168.1.100           # Server IP/hostname
SSH_USER=ubuntu                  # SSH username
SSH_PRIVATE_KEY=<private-key>    # Full SSH private key
DEPLOY_PATH=/var/www/subtracker # Deployment directory

# Application secrets (also in 'production' environment)
JWT_SECRET_KEY=<jwt-secret>
ENCRYPTION_KEY=<fernet-key>
RESEND_API_KEY=<resend-key>
OPENAI_API_KEY=<openai-key>
VAPID_PUBLIC_KEY=<vapid-public>
VAPID_PRIVATE_KEY=<vapid-private>
```

## Production Server Setup

### Initial Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Create deployment directory
sudo mkdir -p /var/www/subtracker
sudo chown $USER:$USER /var/www/subtracker
cd /var/www/subtracker

# Clone repository
git clone https://github.com/Ankirama/Subtracker.git .

# Create environment file
cp .env.example .env.production
nano .env.production  # Configure variables
```

### Traefik Setup

```bash
# Create proxy network
docker network create proxy

# Create traefik directory
mkdir -p traefik
touch traefik/acme.json
chmod 600 traefik/acme.json

# Start Traefik (see Traefik configuration below)
docker compose -f docker-compose.traefik.yml up -d
```

## Deployment Methods

### Automatic (Recommended)

Merge to `main` branch triggers automatic deployment:
1. CI builds and tests
2. CD builds Docker images
3. Pushes to GHCR
4. Deploys to production
5. Runs health checks
6. Auto-rolls back on failure

### Manual Deployment

```bash
# Via GitHub Actions
# Go to: Actions → CD - Deploy to Production → Run workflow

# Or SSH to server
ssh user@server
cd /var/www/subtracker
./deploy-prod.sh latest
```

## Commands

### Check Status

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

### Manual Operations

```bash
# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Restart service
docker compose -f docker-compose.prod.yml restart backend

# Run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Database backup
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U subtracker subtracker_prod > backup.sql
```

### Health Checks

```bash
# API health
curl https://subscriptionstracker.io/api/health

# Frontend
curl https://subscriptionstracker.io

# Internal check
docker compose -f docker-compose.prod.yml exec backend curl http://localhost:8000/health
```

## Rollback

### Automatic Rollback

`deploy-prod.sh` automatically rolls back if:
- Health checks fail
- Migrations fail
- Services don't start

### Manual Rollback

```bash
# List backups
ls -la backups/

# Restore from backup
BACKUP="backups/20250128_120000"
cp "$BACKUP/docker-compose-backup.yml" docker-compose.prod.yml
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# Deploy specific version
./deploy-prod.sh abc123def  # Git commit SHA
./deploy-prod.sh v1.2.3     # Git tag
```

## Troubleshooting

### Deployment Fails

```bash
# 1. Check GitHub Actions logs
# 2. Verify secrets are set
# 3. Check server logs
docker compose logs backend

# Common issues:
# - SSH connection: Check SSH_HOST, SSH_USER, SSH_PRIVATE_KEY
# - Health check: Check .env.production variables
# - Permission: sudo usermod -aG docker $USER
```

### Services Won't Start

```bash
# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs <service>

# Validate config
docker compose -f docker-compose.prod.yml config

# Check resources
df -h && free -m
```

### Database Issues

```bash
# Test connection
docker compose exec backend python -c "from app.database import engine; print(engine.connect())"

# Run migrations
docker compose exec backend alembic upgrade head

# Reset database (⚠️ DESTRUCTIVE)
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
```

## Security

1. Rotate secrets regularly
2. Keep Docker/system updated
3. Monitor logs for suspicious activity
4. Automated daily database backups
5. Use Let's Encrypt for SSL/TLS

## Monitoring

```bash
# All service logs
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend

# Resource usage
docker stats

# Errors
docker compose logs | grep -i error
```

---

**Last Updated:** 2025-01-28  
**For issues:** Check GitHub Issues or contact DevOps team
