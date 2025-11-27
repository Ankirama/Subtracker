# CI/CD Pipeline Setup Guide

Complete guide for setting up GitHub Actions CI/CD pipeline for Subscription Tracker.

## Overview

The CI/CD pipeline consists of three workflows:
1. **CI Workflow** (`.github/workflows/ci.yml`) - Quality & security checks on PRs and main branch
2. **CD Workflow** (`.github/workflows/cd.yml`) - Automated deployment to production
3. **Security Scan** (`.github/workflows/security-scan.yml`) - Scheduled weekly security scans

## Prerequisites

- GitHub repository with write access
- Production server with:
  - Docker and Docker Compose installed
  - SSH access configured
  - Git installed
  - Project cloned to deployment directory

## GitHub Secrets Configuration

### Required Repository Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:

```yaml
# SSH Access for Deployment
SSH_PRIVATE_KEY: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  [Your SSH private key content]
  -----END OPENSSH PRIVATE KEY-----

SSH_HOST: your-server-ip-or-domain
SSH_USER: your-ssh-username
DEPLOY_PATH: /path/to/subscription_tracker

# Optional: Gitleaks License (for secrets detection)
GITLEAKS_LICENSE: your-gitleaks-license-key
```

### Environment Secrets (Production)

Go to: **Settings → Environments → New environment**

Create environment named: `production`

Add these secrets to the production environment:

```yaml
# All secrets from .env.production should be added here
# This ensures sensitive data isn't committed to the repository

POSTGRES_PASSWORD: your-secure-postgres-password
JWT_SECRET_KEY: your-jwt-secret-key
ENCRYPTION_KEY: your-encryption-key
OPENAI_API_KEY: your-openai-api-key
RESEND_API_KEY: your-resend-api-key

# Add any other environment-specific secrets
```

## SSH Key Setup

### 1. Generate SSH Key Pair (on your local machine)

```bash
# Generate new SSH key for deployment
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy

# This creates two files:
# - github_actions_deploy (private key) → Add to GitHub Secrets
# - github_actions_deploy.pub (public key) → Add to server
```

### 2. Add Public Key to Server

```bash
# Copy public key to server
ssh-copy-id -i ~/.ssh/github_actions_deploy.pub user@your-server

# Or manually add to server:
cat ~/.ssh/github_actions_deploy.pub | ssh user@your-server "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### 3. Add Private Key to GitHub Secrets

```bash
# Display private key
cat ~/.ssh/github_actions_deploy

# Copy entire output (including BEGIN/END lines) and paste into GitHub Secret: SSH_PRIVATE_KEY
```

### 4. Test SSH Connection

```bash
# Test connection
ssh -i ~/.ssh/github_actions_deploy user@your-server "echo 'SSH connection successful!'"
```

## Server Setup

### 1. Prepare Deployment Directory

```bash
# SSH into your server
ssh user@your-server

# Clone repository (if not already done)
cd /path/to/deployment
git clone https://github.com/yourusername/subscription-tracker.git
cd subscription-tracker

# Create .env.production file
cp .env.production.example .env.production

# Edit and configure .env.production
nano .env.production

# Set proper permissions
chmod 600 .env.production

# Create required directories
mkdir -p backups logs
```

### 2. Docker Setup

```bash
# Ensure Docker is installed and running
docker --version
docker compose version

# Create Docker network for Traefik (if using)
docker network create proxy

# Test Docker Compose configuration
docker compose -f docker-compose.prod.yml config
```

### 3. GitHub Container Registry Authentication

```bash
# Login to GHCR on server
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Create .docker/config.json for automated pulls
mkdir -p ~/.docker
```

## GitHub Container Registry Setup

### 1. Enable Packages

Go to: **Settings → Developer settings → Personal access tokens → Tokens (classic)**

Create new token with scopes:
- `write:packages`
- `read:packages`
- `delete:packages`

Add token to GitHub Secrets as `GITHUB_TOKEN` (if not already available)

### 2. Configure Image Visibility

Go to: **Packages** (on your profile or organization)

For each package (backend, frontend):
- Click package name
- **Package settings → Change visibility**
- Set to "Public" or configure access for your server

## Workflow Configuration

### CI Workflow Triggers

```yaml
# Runs on:
- Pull requests to main/develop
- Pushes to main branch
```

**What it does:**
- Python linting (black, ruff)
- Frontend linting (ESLint)
- Type checking (mypy, TypeScript)
- Security scanning (Strix, pip-audit, npm audit, Gitleaks)
- Run tests (pytest, vitest)
- Database migration validation

### CD Workflow Triggers

```yaml
# Runs on:
- Push to main branch (auto-deploy)
- Manual trigger (workflow_dispatch)
```

**What it does:**
- Build Docker images
- Push to GitHub Container Registry
- SSH to production server
- Pull latest code and images
- Stop → Pull → Build → Start (simple deployment)
- Run database migrations
- Health checks
- Automatic rollback on failure

### Security Scan Triggers

```yaml
# Runs on:
- Schedule: Every Monday at 9:00 AM UTC
- Manual trigger (workflow_dispatch)
```

**What it does:**
- Dependency vulnerability scanning
- Code security analysis (Strix)
- Secrets detection (Gitleaks)
- Docker image scanning (Trivy)
- Generate security reports

## Testing the Pipeline

### 1. Test CI Workflow

```bash
# Create feature branch
git checkout -b test/ci-pipeline

# Make a small change
echo "# Test" >> README.md

# Commit and push
git add README.md
git commit -m "test: CI pipeline"
git push origin test/ci-pipeline

# Create pull request on GitHub
# CI workflow should run automatically
```

### 2. Test CD Workflow (Staging)

```bash
# First test with a staging environment
# Or test with manual trigger

# Go to: Actions → CD - Deploy to Production → Run workflow
# Select branch: main
# Click "Run workflow"
```

### 3. Monitor Deployment

```bash
# On your local machine, watch GitHub Actions
# Or SSH to server and monitor:

ssh user@your-server
cd /path/to/subscription_tracker

# Watch logs
docker compose -f docker-compose.prod.yml logs -f

# Check service status
docker compose -f docker-compose.prod.yml ps

# Check application health
curl https://subscriptionstracker.io/health
```

## Troubleshooting

### Common Issues

#### 1. SSH Connection Failed

```bash
# Check SSH key is correct
ssh -i ~/.ssh/github_actions_deploy user@your-server

# Verify host key
ssh-keyscan -H your-server >> ~/.ssh/known_hosts

# Check server SSH logs
sudo tail -f /var/log/auth.log
```

#### 2. Docker Login Failed

```bash
# Verify GitHub token has package permissions
# Re-login to GHCR on server
echo "YOUR_TOKEN" | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Check Docker credentials
cat ~/.docker/config.json
```

#### 3. Health Check Failed

```bash
# Check backend logs
docker compose -f docker-compose.prod.yml logs backend --tail=100

# Check if backend is responding internally
docker compose -f docker-compose.prod.yml exec backend curl http://localhost:8000/health

# Check database connection
docker compose -f docker-compose.prod.yml exec backend alembic current
```

#### 4. Migration Failed

```bash
# Check migration status
docker compose -f docker-compose.prod.yml exec backend alembic current

# Check for conflicts
docker compose -f docker-compose.prod.yml exec backend alembic branches

# Manually run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Check backend logs
docker compose -f docker-compose.prod.yml logs backend | grep -i alembic
```

#### 5. Secrets Not Found

```bash
# Verify secrets are set in GitHub
# Settings → Secrets and variables → Actions

# For environment secrets, check:
# Settings → Environments → production → Secrets

# Test secret availability (in workflow)
- name: Test secrets
  run: |
    echo "SSH_HOST is set: ${{ secrets.SSH_HOST != '' }}"
```

### Rollback Procedure

If deployment fails and automatic rollback doesn't work:

```bash
# SSH to server
ssh user@your-server
cd /path/to/subscription_tracker

# Find latest backup
ls -lt backups/

# Rollback to specific version
git checkout <previous-commit-hash>

# Restart services
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# Or restore from backup
cd backups/<backup-timestamp>
cp docker-compose-backup.yml ../../docker-compose.prod.yml
cd ../..
docker compose -f docker-compose.prod.yml up -d

# Restore database if needed
docker compose -f docker-compose.prod.yml exec -T postgres psql -U subscriptions subscriptions < backups/<backup-timestamp>/database-backup.sql
```

## Security Best Practices

### 1. Dedicated Deploy User (Critical)

Create a restricted deployment user on your production server:

```bash
# Create deploy user with no login shell (optional for max security)
sudo useradd -m -s /bin/bash deploy  # With shell access
# OR
sudo useradd -m -s /usr/sbin/nologin deploy  # No shell (forced command only)

# Create .ssh directory
sudo mkdir -p /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh

# Add GitHub Actions public key
sudo nano /home/deploy/.ssh/authorized_keys
# Paste your github_actions_deploy.pub key

# Set permissions
sudo chmod 600 /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh

# Grant deploy user Docker permissions
sudo usermod -aG docker deploy

# Grant specific sudo permissions for deployment (optional)
sudo visudo -f /etc/sudoers.d/deploy
```

**Restricted SSH Configuration** (`/home/deploy/.ssh/authorized_keys`):

```bash
# Option 1: Forced command (most secure - no shell access)
command="/home/deploy/deployment-script.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAAC3... github-actions-deploy

# Option 2: Restricted commands only (medium security)
restrict,command="/bin/bash" ssh-ed25519 AAAAC3... github-actions-deploy

# Option 3: Standard key (least restrictive)
ssh-ed25519 AAAAC3... github-actions-deploy
```

**Benefits:**
- Separate from your personal user account
- Audit trail for deployment activities
- Can be disabled without affecting admin access
- Restricted permissions reduce blast radius

### 2. Secret Scope Limitation

#### Separate SSH Keys per Environment

```bash
# Development/Staging
ssh-keygen -t ed25519 -C "github-actions-staging" -f ~/.ssh/github_actions_staging

# Production
ssh-keygen -t ed25519 -C "github-actions-production" -f ~/.ssh/github_actions_production

# Add to respective GitHub environments
# Staging environment: SSH_PRIVATE_KEY_STAGING
# Production environment: SSH_PRIVATE_KEY_PRODUCTION
```

**In GitHub Workflow:**

```yaml
- name: Setup SSH
  run: |
    mkdir -p ~/.ssh
    # Use environment-specific key
    echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
    chmod 600 ~/.ssh/deploy_key
```

#### Database User Segregation

Create separate PostgreSQL users with minimal privileges:

```sql
-- CI/Testing user (read-only for validation)
CREATE USER ci_user WITH PASSWORD 'ci_password';
GRANT CONNECT ON DATABASE subscriptions TO ci_user;
GRANT USAGE ON SCHEMA public TO ci_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ci_user;

-- Application user (read/write, no DDL)
CREATE USER app_user WITH PASSWORD 'app_password';
GRANT CONNECT ON DATABASE subscriptions TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Migration user (DDL for schema changes)
CREATE USER migration_user WITH PASSWORD 'migration_password';
GRANT ALL PRIVILEGES ON DATABASE subscriptions TO migration_user;

-- Admin user (full access, manual operations only)
CREATE USER admin_user WITH PASSWORD 'admin_password' SUPERUSER;
```

**Update `.env.production`:**

```bash
# Application runtime
DATABASE_URL=postgresql://app_user:app_password@postgres:5432/subscriptions

# For migrations (only during deployment)
MIGRATION_DATABASE_URL=postgresql://migration_user:migration_password@postgres:5432/subscriptions
```

**Update CD Workflow:**

```yaml
- name: Run database migrations
  env:
    DATABASE_URL: ${{ secrets.MIGRATION_DATABASE_URL }}
  run: |
    docker compose exec -T backend alembic upgrade head
```

### 3. Secret Rotation Policy

Rotate secrets immediately after:

#### Team Changes
```bash
# When adding collaborators
- Generate new deployment SSH key
- Update GitHub secret SSH_PRIVATE_KEY
- Update authorized_keys on server
- Revoke old key

# When removing collaborators
- Rotate ALL secrets they had access to
- Review GitHub Actions logs for their activity
- Audit recent deployments
```

#### Infrastructure Changes
```bash
# When changing runners
- Rotate GitHub tokens
- Regenerate SSH keys
- Update database passwords
- Rotate encryption keys (requires data re-encryption)

# After security incidents
- Immediate rotation of ALL secrets
- Review audit logs
- Force re-authentication
```

#### Regular Rotation Schedule
```bash
# Every 90 days (automated reminder)
- SSH keys
- Database passwords
- API tokens (OpenAI, Resend, etc.)
- GitHub personal access tokens

# Every 180 days
- JWT secret keys (requires user re-login)
- Encryption keys (requires data migration)
```

**Automation Script** (`scripts/rotate-secrets.sh`):

```bash
#!/bin/bash
# Secret rotation reminder and tracking

LAST_ROTATION_FILE="/var/log/deployment/last-secret-rotation"
DAYS_SINCE_ROTATION=$(( ($(date +%s) - $(stat -f %m "$LAST_ROTATION_FILE" 2>/dev/null || echo 0)) / 86400 ))

if [ $DAYS_SINCE_ROTATION -gt 90 ]; then
    echo "⚠️  WARNING: Secrets are $DAYS_SINCE_ROTATION days old"
    echo "ACTION REQUIRED: Rotate the following:"
    echo "  - SSH deployment keys"
    echo "  - Database passwords"
    echo "  - API tokens"
    echo "  - GitHub tokens"
    exit 1
fi
```

### 4. Self-Hosted Runners Security

If using self-hosted GitHub Actions runners:

#### Runner Hardening

```bash
# Create dedicated runner user
sudo useradd -m -s /bin/bash github-runner
sudo usermod -aG docker github-runner

# Restrict runner permissions
sudo mkdir -p /opt/github-runner
sudo chown github-runner:github-runner /opt/github-runner
sudo chmod 750 /opt/github-runner

# Install runner as service
cd /opt/github-runner
sudo -u github-runner ./svc.sh install
sudo -u github-runner ./svc.sh start
```

#### Critical Security Measures

1. **Ephemeral Runners (Recommended)**
   ```yaml
   # Use ephemeral runners that are destroyed after each job
   runs-on: self-hosted-ephemeral
   ```

2. **Network Isolation**
   ```bash
   # Isolate runners in separate network
   # Only allow outbound HTTPS
   # No inbound connections except from GitHub
   ```

3. **Credential Management**
   ```bash
   # Store secrets on runner, not in GitHub
   # Use HashiCorp Vault or AWS Secrets Manager

   # Example: Vault integration
   - name: Get secrets from Vault
     run: |
       export VAULT_ADDR="https://vault.internal"
       export DB_PASSWORD=$(vault kv get -field=password secret/production/db)
   ```

4. **Runner Compromise = High Risk**
   ```
   If a runner is compromised:
   ✓ Attacker gets: All checked-out code
   ✓ Attacker gets: Secrets in workflow environment
   ✓ Attacker gets: Access to runner's network
   ✗ Attacker doesn't get: GitHub Secrets (unless exposed)

   Mitigation:
   - Use ephemeral runners
   - Minimal permissions
   - Network segmentation
   - Regular security scans
   - Audit logs
   ```

5. **Runner Monitoring**
   ```bash
   # Monitor runner activity
   sudo journalctl -u actions.runner.* -f

   # Alert on suspicious activity
   # - Unusual network connections
   # - Unexpected processes
   # - Failed authentication attempts
   ```

### 5. GitHub-Hosted Runners (Recommended for Most Cases)

**Advantages:**
- Isolated ephemeral environment
- No infrastructure maintenance
- Automatic security updates
- Lower compromise risk

**Secrets Management:**
```yaml
# Use environment protection rules
environment:
  name: production
  # Require approval for production deployments
  # Limit approvers to specific users
```

### 6. Additional Hardening

#### Branch Protection Rules

```
Settings → Branches → Add rule for 'main':
✓ Require pull request reviews (1+ approvers)
✓ Require status checks (CI must pass)
✓ Require branches to be up to date
✓ Require signed commits (optional)
✓ Include administrators
✓ Restrict who can push (admin only)
```

#### Environment Protection Rules

```
Settings → Environments → production:
✓ Required reviewers: [specific users]
✓ Wait timer: 5 minutes (allows cancellation)
✓ Deployment branches: main only
✓ Environment secrets: production-only secrets
```

#### Workflow Permissions

```yaml
# In workflow file
permissions:
  contents: read       # Read repository contents
  packages: write      # Push to GHCR
  # Minimize other permissions
```

#### Audit and Monitoring

```bash
# Review GitHub audit log
Settings → Security → Audit log

# Monitor for:
- Secret access patterns
- Workflow modifications
- Failed deployments
- Unusual SSH activity
- Database connection attempts

# Set up alerts
- Failed login attempts > 3
- Workflow failures > 5/day
- Secret rotation overdue
- Unauthorized access attempts
```

### 7. Security Checklist

Before going to production:

```
Infrastructure:
☐ Dedicated deploy user created
☐ SSH key restricted with forced command
☐ Firewall rules configured
☐ Network segmentation in place

Secrets:
☐ All secrets stored in GitHub Secrets
☐ Environment-specific secrets separated
☐ Database users segregated by role
☐ Rotation schedule documented
☐ No secrets in code or logs

Access Control:
☐ Branch protection rules enabled
☐ Environment protection configured
☐ Deployment approvers defined
☐ Audit logging enabled

Monitoring:
☐ Security scan workflows active
☐ Failed deployment alerts configured
☐ Audit log review scheduled
☐ Incident response plan documented

Compliance:
☐ Security policy documented
☐ Incident response procedures defined
☐ Backup/restore tested
☐ Disaster recovery plan ready
```

## Workflow Optimization

### Caching Strategy

The workflows use caching to speed up builds:
- Python dependencies cached by `setup-python`
- Node dependencies cached by `setup-node`
- Docker layers cached in GHCR

### Parallel Execution

CI jobs run in parallel:
- Backend quality checks
- Frontend quality checks
- Migration validation
- Secrets scanning

This reduces total CI time from ~15min to ~5min.

### Resource Limits

Default timeouts:
- CI jobs: 30 minutes
- CD jobs: 45 minutes
- Security scans: 60 minutes

Adjust in workflow files if needed:

```yaml
jobs:
  job-name:
    timeout-minutes: 30
```

## Monitoring and Alerts

### GitHub Actions Notifications

Enable notifications:
- **Settings → Notifications → Actions**
- Enable "Send notifications for failed workflows"

### Production Monitoring

Set up external monitoring:
- UptimeRobot for endpoint monitoring
- Sentry for error tracking
- Datadog/Prometheus for metrics

### Deployment Notifications

Consider adding Slack/Discord notifications:

```yaml
- name: Notify deployment
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Maintenance

### Weekly Tasks
- Review security scan reports
- Check for dependency updates
- Monitor CI/CD success rates

### Monthly Tasks
- Review and cleanup old Docker images
- Audit GitHub Actions usage
- Review and optimize workflow performance

### Quarterly Tasks
- Rotate production secrets
- Update workflow actions to latest versions
- Review and update this documentation

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Alembic Migrations Guide](https://alembic.sqlalchemy.org/)
- [Strix Security Scanner](https://github.com/usestrix/strix)
- [Gitleaks Secrets Detection](https://github.com/gitleaks/gitleaks)

## Support

For issues with the CI/CD pipeline:
1. Check workflow logs in GitHub Actions
2. Review server logs via SSH
3. Consult troubleshooting section above
4. Check project repository issues

---

**Last Updated:** 2025-11-27
**Pipeline Version:** 1.0.0
