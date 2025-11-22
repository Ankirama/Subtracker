# Production Deployment Guide

This guide walks you through deploying Subscription Tracker to production on your Ubuntu server with Traefik reverse proxy.

## Prerequisites

- Ubuntu server (tested on Ubuntu 22.04+)
- Docker and Docker Compose installed
- **Traefik reverse proxy already running** (with `proxy` network and `mytlschallenge` certresolver)
- Domain name pointed to your server (`subtracker.ankirama.com`)
- SSH access to your server

## Server Requirements

- **CPU**: 2+ cores (recommended)
- **RAM**: 8GB minimum
- **Storage**: 20GB+ for application and backups

## Quick Start

```bash
# 1. Clone the repository on your server
git clone <your-repo-url> /opt/subscription-tracker
cd /opt/subscription-tracker

# 2. Copy and configure environment
cp .env.production.example .env.production
nano .env.production  # Edit with your values

# 3. Generate secrets
openssl rand -hex 32  # For JWT_SECRET_KEY
openssl rand -base64 32  # For ENCRYPTION_KEY

# 4. Deploy
./scripts/deploy.sh
```

## Detailed Setup

### Step 1: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker (if not installed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### Step 2: DNS Configuration

Point your domain to your server's IP address:

1. Go to your DNS provider (e.g., Cloudflare, Route53)
2. Add an A record:
   - **Name**: `subtracker` (or your subdomain)
   - **Type**: A
   - **Value**: Your server's public IP
   - **TTL**: Auto or 300

Wait for DNS propagation (usually 5-30 minutes).

### Step 3: Configure Environment

Copy the example environment file and configure it:

```bash
cp .env.production.example .env.production
nano .env.production
```

**Critical settings to change:**

```bash
# Security - MUST CHANGE
POSTGRES_PASSWORD=<generate-strong-password>
JWT_SECRET_KEY=<run: openssl rand -hex 32>
ENCRYPTION_KEY=<run: openssl rand -base64 32>

# Domain (for Traefik integration)
DOMAIN_NAME=ankirama.com
SUBDOMAIN=subtracker
FRONTEND_URL=https://subtracker.ankirama.com
CORS_ORIGINS=https://subtracker.ankirama.com

# OpenAI API
OPENAI_API_KEY=sk-your-actual-key

# SendGrid (for emails)
SENDGRID_API_KEY=SG.your-actual-key

# VAPID keys for push notifications
# Generate with: npx web-push generate-vapid-keys
VAPID_PUBLIC_KEY=<your-public-key>
VAPID_PRIVATE_KEY=<your-private-key>
```

### Step 4: Deploy

Run the deployment script:

```bash
./scripts/deploy.sh
```

This will:
1. Validate your environment configuration
2. Build Docker images
3. Start all services
4. Run database migrations
5. Obtain SSL certificate (first run only)

### Step 5: Create First Admin User

For the first user (admin), you need to temporarily disable invite requirement or create a direct database entry:

**Option A: Temporary disable invite (recommended for first user)**

```bash
# Edit .env.production temporarily
nano .env.production
# Set: REQUIRE_INVITE_TOKEN=False

# Restart backend
docker compose -f docker-compose.prod.yml restart backend

# Register your admin account via the app
# Then re-enable invite requirement
nano .env.production
# Set: REQUIRE_INVITE_TOKEN=True

# Restart backend again
docker compose -f docker-compose.prod.yml restart backend

# Make user admin via database
docker compose -f docker-compose.prod.yml exec postgres psql -U subscriptions -d subscriptions -c "UPDATE users SET is_admin = true WHERE email = 'your-email@example.com';"
```

**Option B: Create admin directly in database**

```bash
# Generate password hash (Python required)
python3 -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"

# Insert user
docker compose -f docker-compose.prod.yml exec postgres psql -U subscriptions -d subscriptions
```

```sql
INSERT INTO users (id, email, password_hash, is_active, is_admin, is_email_verified, created_at, updated_at)
VALUES (gen_random_uuid(), 'admin@example.com', '<paste-hash-here>', true, true, true, NOW(), NOW());
```

### Step 6: Create Invite Links

Once you have an admin account:

1. Log in to the application
2. Go to Admin > Invites
3. Click "Create Invite"
4. Share the invite link with users you want to register

## Maintenance

### Viewing Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f celery-worker
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Backups

**Manual backup:**
```bash
./scripts/backup.sh
```

**Setup automated daily backups:**
```bash
# Add to crontab
crontab -e

# Add this line (runs at 2 AM daily)
0 2 * * * /opt/subscription-tracker/scripts/backup.sh >> /var/log/subtracker-backup.log 2>&1
```

**Restore from backup:**
```bash
./scripts/restore.sh subtracker_db_20241122_020000.sql.gz
```

### SSL Certificate Renewal

SSL certificates are managed automatically by Traefik using Let's Encrypt. No manual intervention is required - Traefik handles certificate renewal automatically.

### Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and redeploy
./scripts/deploy.sh
```

## Troubleshooting

### Service won't start

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Check logs for specific service
docker compose -f docker-compose.prod.yml logs backend
```

### Database connection issues

```bash
# Check postgres is running
docker compose -f docker-compose.prod.yml exec postgres pg_isready

# Check database exists
docker compose -f docker-compose.prod.yml exec postgres psql -U subscriptions -l
```

### SSL certificate issues

SSL is handled by Traefik. Check Traefik's logs if you encounter certificate issues:

```bash
# Check your Traefik container logs
docker logs traefik

# Verify domain is accessible via Traefik
curl -I https://subtracker.ankirama.com/health
```

### High memory usage

```bash
# Check container resource usage
docker stats

# Restart services
docker compose -f docker-compose.prod.yml restart
```

## Security Checklist

- [ ] Strong database password set
- [ ] JWT_SECRET_KEY generated with openssl
- [ ] ENCRYPTION_KEY generated with openssl
- [ ] SSL certificate obtained and working
- [ ] REQUIRE_INVITE_TOKEN set to True
- [ ] Firewall configured (only ports 80, 443 open)
- [ ] SSH key authentication (password auth disabled)
- [ ] Regular backups configured
- [ ] .env.production file permissions restricted (`chmod 600`)

## Firewall Setup (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               Traefik (External - Port 80, 443)             │
│    SSL Termination + Reverse Proxy (shared with n8n, etc)   │
└─────────────────────────────────────────────────────────────┘
                    │                    │
                    ▼                    ▼
        ┌───────────────────┐  ┌───────────────────┐
        │      Frontend     │  │      Backend      │
        │  (React + Nginx)  │  │    (FastAPI)      │
        └───────────────────┘  └───────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
          ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
          │  PostgreSQL │     │    Redis    │     │   Celery    │
          │  (Database) │     │   (Cache)   │     │  (Workers)  │
          └─────────────┘     └─────────────┘     └─────────────┘
```

## Support

For issues or questions, check the logs first, then create an issue in the repository.
