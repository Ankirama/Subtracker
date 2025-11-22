# Environment Variables Documentation

Complete reference for environment variables required by the Subscription Tracker application, including the new Cancellation Workflows feature.

## Table of Contents
1. [Backend Environment Variables](#backend-environment-variables)
2. [Frontend Environment Variables](#frontend-environment-variables)
3. [Development Setup](#development-setup)
4. [Production Setup](#production-setup)
5. [Docker Configuration](#docker-configuration)
6. [Security Best Practices](#security-best-practices)

---

## Backend Environment Variables

### Core Application Settings

#### `DATABASE_URL` (Required)
**Description:** PostgreSQL database connection string

**Format:** `postgresql://user:password@host:port/database`

**Example:**
```bash
# Development
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/subscription_tracker

# Production
DATABASE_URL=postgresql://prod_user:secure_password@db.example.com:5432/subscription_tracker
```

**Notes:**
- Must include credentials with read/write permissions
- Ensure database exists before starting application
- SSL mode recommended for production: `?sslmode=require`

---

#### `JWT_SECRET_KEY` (Required)
**Description:** Secret key for JWT token signing and verification

**Format:** String (minimum 32 characters recommended)

**Example:**
```bash
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production-min-32-chars
```

**Generation:**
```bash
# Generate a secure random key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Security Notes:**
- ⚠️ **CRITICAL**: Never commit to version control
- Must be identical across all backend instances
- Changing this will invalidate all existing user sessions
- Minimum 32 characters, 64+ recommended for production

---

#### `JWT_ALGORITHM` (Optional)
**Description:** Algorithm used for JWT token encoding

**Default:** `HS256`

**Example:**
```bash
JWT_ALGORITHM=HS256
```

**Valid Options:**
- `HS256` (HMAC with SHA-256) - Recommended for most use cases
- `HS512` (HMAC with SHA-512) - More secure, slightly slower
- `RS256` (RSA with SHA-256) - For distributed systems (requires public/private key pair)

---

#### `FRONTEND_URL` (Required)
**Description:** Frontend application URL for CORS configuration

**Format:** Full URL with protocol

**Example:**
```bash
# Development
FRONTEND_URL=http://localhost:5175

# Production
FRONTEND_URL=https://app.your-domain.com
```

**Notes:**
- Used for CORS (Cross-Origin Resource Sharing) configuration
- Must match exactly (including protocol and port)
- Multiple URLs can be separated by commas if needed

---

### AI & OpenAI Integration

#### `OPENAI_API_KEY` (Required for Cancellation Feature)
**Description:** OpenAI API key for AI-powered cancellation research

**Format:** `sk-...` (starts with "sk-")

**Example:**
```bash
OPENAI_API_KEY=sk-proj-abc123...xyz789
```

**Obtain From:**
1. Visit https://platform.openai.com/api-keys
2. Create new secret key
3. Copy immediately (only shown once)
4. Set up billing at https://platform.openai.com/account/billing

**Cost Considerations:**
- GPT-4: ~$0.08 per cancellation research request
- With 30-day caching: Reduces costs by >95%
- Recommended budget: $50-200/month depending on user base
- Set up usage limits on OpenAI dashboard

**Security Notes:**
- ⚠️ **CRITICAL**: Never commit to version control
- Store securely (environment variable or secrets manager)
- Never expose in API responses or logs
- Rotate periodically for security

---

#### `OPENAI_MODEL` (Optional)
**Description:** OpenAI model to use for cancellation research

**Default:** `gpt-4`

**Example:**
```bash
OPENAI_MODEL=gpt-4
```

**Valid Options:**
- `gpt-4` - Most accurate, higher cost (~$0.08/request)
- `gpt-4-turbo` - Faster, slightly cheaper
- `gpt-3.5-turbo` - Cheapest but less accurate (not recommended)

**Notes:**
- GPT-4 recommended for best accuracy
- Cheaper models may produce lower quality instructions
- Test thoroughly if changing from default

---

#### `CANCELLATION_CACHE_DAYS` (Optional)
**Description:** Number of days to cache AI-generated cancellation research

**Default:** `30`

**Example:**
```bash
CANCELLATION_CACHE_DAYS=30
```

**Considerations:**
- Higher value = Lower OpenAI costs, potentially outdated info
- Lower value = Higher accuracy, increased API costs
- Recommended: 30 days balances cost and freshness
- Consider 7 days if provider procedures change frequently

---

### Email Integration

#### `MAIL_SERVER` (Required for email features)
**Description:** SMTP server hostname for sending emails

**Example:**
```bash
MAIL_SERVER=smtp.gmail.com
```

---

#### `MAIL_PORT` (Required for email features)
**Description:** SMTP server port

**Default:** `587` (TLS) or `465` (SSL)

**Example:**
```bash
MAIL_PORT=587
```

---

#### `MAIL_USERNAME` (Required for email features)
**Description:** SMTP authentication username

**Example:**
```bash
MAIL_USERNAME=your-email@gmail.com
```

---

#### `MAIL_PASSWORD` (Required for email features)
**Description:** SMTP authentication password

**Example:**
```bash
MAIL_PASSWORD=your-app-specific-password
```

**Security Notes:**
- Use app-specific passwords (not account password)
- Store securely in environment or secrets manager

---

#### `MAIL_FROM` (Required for email features)
**Description:** Default "From" email address

**Example:**
```bash
MAIL_FROM=noreply@your-domain.com
```

---

### Celery & Redis (Background Tasks)

#### `REDIS_URL` (Required for Celery)
**Description:** Redis connection URL for Celery task queue

**Format:** `redis://host:port/db`

**Example:**
```bash
# Development
REDIS_URL=redis://localhost:6379/0

# Production
REDIS_URL=redis://:password@redis.example.com:6379/0
```

---

### API Rate Limiting

#### `RATE_LIMIT_REVIEW_SUGGESTIONS` (Optional)
**Description:** Rate limit for review suggestions endpoint

**Default:** `60/minute`

**Example:**
```bash
RATE_LIMIT_REVIEW_SUGGESTIONS=60/minute
```

---

#### `RATE_LIMIT_CANCELLATION_RESEARCH` (Optional)
**Description:** Rate limit for AI cancellation research (more expensive)

**Default:** `10/minute`

**Example:**
```bash
RATE_LIMIT_CANCELLATION_RESEARCH=10/minute
```

**Notes:**
- Lower limit for AI endpoints to control costs
- Adjust based on OpenAI budget and user needs

---

### Logging & Monitoring

#### `LOG_LEVEL` (Optional)
**Description:** Application logging level

**Default:** `INFO`

**Example:**
```bash
# Development
LOG_LEVEL=DEBUG

# Production
LOG_LEVEL=INFO
```

**Valid Options:**
- `DEBUG` - Verbose logging (development only)
- `INFO` - Standard logging (production default)
- `WARNING` - Only warnings and errors
- `ERROR` - Only errors
- `CRITICAL` - Only critical issues

---

#### `SENTRY_DSN` (Optional)
**Description:** Sentry error tracking DSN

**Example:**
```bash
SENTRY_DSN=https://abc123@o123456.ingest.sentry.io/789012
```

**Notes:**
- Recommended for production error tracking
- Obtain from https://sentry.io project settings

---

### Performance & Optimization

#### `WORKERS` (Optional)
**Description:** Number of Gunicorn workers for production

**Default:** `4`

**Example:**
```bash
WORKERS=4
```

**Calculation:**
```bash
# Recommended formula
WORKERS = (2 x num_cores) + 1
```

---

#### `MAX_CONNECTIONS` (Optional)
**Description:** Maximum database connection pool size

**Default:** `20`

**Example:**
```bash
MAX_CONNECTIONS=20
```

---

## Frontend Environment Variables

### API Configuration

#### `VITE_API_URL` (Required)
**Description:** Backend API base URL

**Format:** Full URL with protocol (no trailing slash)

**Example:**
```bash
# Development
VITE_API_URL=http://localhost:8000

# Production
VITE_API_URL=https://api.your-domain.com
```

**Notes:**
- Must be prefixed with `VITE_` for Vite to expose to client
- No trailing slash
- Must be accessible from user's browser

---

### Optional Frontend Variables

#### `VITE_APP_NAME` (Optional)
**Description:** Application name for branding

**Default:** `Subscription Tracker`

**Example:**
```bash
VITE_APP_NAME=Subscription Tracker
```

---

#### `VITE_ENABLE_ANALYTICS` (Optional)
**Description:** Enable analytics tracking

**Default:** `false`

**Example:**
```bash
VITE_ENABLE_ANALYTICS=true
```

---

## Development Setup

### Quick Start

1. **Clone repository:**
   ```bash
   git clone https://github.com/your-org/subscription-tracker.git
   cd subscription-tracker
   ```

2. **Backend setup:**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env with your values
   ```

3. **Frontend setup:**
   ```bash
   cd frontend
   cp .env.example .env
   # Edit .env with your values
   ```

### Example `.env` Files

#### Backend `.env.example`
```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/subscription_tracker

# JWT Authentication
JWT_SECRET_KEY=dev-secret-key-change-in-production-min-32-characters
JWT_ALGORITHM=HS256

# Frontend CORS
FRONTEND_URL=http://localhost:5175

# OpenAI (Required for Cancellation Feature)
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4
CANCELLATION_CACHE_DAYS=30

# Email (Optional - for notifications)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=noreply@localhost

# Redis (Optional - for background tasks)
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=DEBUG
```

#### Frontend `.env.example`
```bash
# API Configuration
VITE_API_URL=http://localhost:8000

# Optional
VITE_APP_NAME=Subscription Tracker
VITE_ENABLE_ANALYTICS=false
```

---

## Production Setup

### Recommended Approach

**Use a secrets manager:**
- AWS Secrets Manager
- Azure Key Vault
- Google Cloud Secret Manager
- HashiCorp Vault

**Example with AWS Secrets Manager:**
```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# In your app initialization
secrets = get_secret('subscription-tracker/prod')
DATABASE_URL = secrets['DATABASE_URL']
OPENAI_API_KEY = secrets['OPENAI_API_KEY']
```

### Environment-Specific Variables

#### Development
```bash
LOG_LEVEL=DEBUG
FRONTEND_URL=http://localhost:5175
VITE_API_URL=http://localhost:8000
```

#### Staging
```bash
LOG_LEVEL=INFO
FRONTEND_URL=https://staging.your-domain.com
VITE_API_URL=https://api-staging.your-domain.com
SENTRY_DSN=https://...@sentry.io/staging-project
```

#### Production
```bash
LOG_LEVEL=INFO
FRONTEND_URL=https://app.your-domain.com
VITE_API_URL=https://api.your-domain.com
SENTRY_DSN=https://...@sentry.io/prod-project
WORKERS=8
MAX_CONNECTIONS=50
```

---

## Docker Configuration

### docker-compose.yml Environment

```yaml
version: '3.8'

services:
  backend:
    image: subscription-tracker-backend:latest
    environment:
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/subscription_tracker
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - FRONTEND_URL=${FRONTEND_URL}
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env

  frontend:
    image: subscription-tracker-frontend:latest
    environment:
      - VITE_API_URL=${VITE_API_URL}
    env_file:
      - .env.frontend

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=subscription_tracker
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### .env for Docker Compose
```bash
# Docker Compose specific
DB_PASSWORD=secure-db-password
JWT_SECRET_KEY=your-jwt-secret-key
OPENAI_API_KEY=sk-your-openai-key
FRONTEND_URL=http://localhost:5175
VITE_API_URL=http://localhost:8000
```

---

## Security Best Practices

### 1. Never Commit Secrets
```bash
# Add to .gitignore
.env
.env.local
.env.*.local
*.pem
*.key
```

### 2. Use Strong Keys
```bash
# Generate secure JWT secret
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate secure password
openssl rand -base64 32
```

### 3. Rotate Secrets Regularly
- JWT secrets: Quarterly (will invalidate all sessions)
- OpenAI API keys: Annually or after any suspected compromise
- Database passwords: Annually
- Email passwords: When changed on provider

### 4. Principle of Least Privilege
- Database user: Only necessary permissions
- OpenAI API key: Set usage limits
- Email account: App-specific password, not main password

### 5. Environment Separation
- Separate keys/secrets per environment (dev/staging/prod)
- Never use production keys in development
- Separate OpenAI API keys per environment for cost tracking

### 6. Audit & Monitoring
- Log environment variable access (not values)
- Monitor OpenAI API usage for anomalies
- Alert on unusual database connection patterns
- Track failed authentication attempts

---

## Validation & Testing

### Validate Environment on Startup

```python
# app/config.py
from pydantic import BaseSettings, validator
import sys

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    OPENAI_API_KEY: str
    FRONTEND_URL: str

    @validator('JWT_SECRET_KEY')
    def validate_jwt_key(cls, v):
        if len(v) < 32:
            raise ValueError('JWT_SECRET_KEY must be at least 32 characters')
        return v

    @validator('OPENAI_API_KEY')
    def validate_openai_key(cls, v):
        if not v.startswith('sk-'):
            raise ValueError('OPENAI_API_KEY must start with "sk-"')
        return v

    class Config:
        env_file = '.env'

try:
    settings = Settings()
except Exception as e:
    print(f"Environment validation failed: {e}")
    sys.exit(1)
```

### Test Script

```bash
#!/bin/bash
# test_env.sh - Validate all required environment variables

echo "Testing environment configuration..."

# Backend required variables
BACKEND_REQUIRED=(
  "DATABASE_URL"
  "JWT_SECRET_KEY"
  "OPENAI_API_KEY"
  "FRONTEND_URL"
)

# Frontend required variables
FRONTEND_REQUIRED=(
  "VITE_API_URL"
)

# Check backend variables
for var in "${BACKEND_REQUIRED[@]}"; do
  if [ -z "${!var}" ]; then
    echo "❌ Missing required backend variable: $var"
    exit 1
  else
    echo "✅ $var is set"
  fi
done

# Check frontend variables
for var in "${FRONTEND_REQUIRED[@]}"; do
  if [ -z "${!var}" ]; then
    echo "❌ Missing required frontend variable: $var"
    exit 1
  else
    echo "✅ $var is set"
  fi
done

# Validate JWT secret length
if [ ${#JWT_SECRET_KEY} -lt 32 ]; then
  echo "❌ JWT_SECRET_KEY must be at least 32 characters"
  exit 1
fi

# Test database connection
python -c "from sqlalchemy import create_engine; create_engine('$DATABASE_URL').connect()" 2>/dev/null
if [ $? -eq 0 ]; then
  echo "✅ Database connection successful"
else
  echo "❌ Database connection failed"
  exit 1
fi

# Test OpenAI API key
curl -s -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models >/dev/null
if [ $? -eq 0 ]; then
  echo "✅ OpenAI API key valid"
else
  echo "❌ OpenAI API key invalid"
  exit 1
fi

echo "✅ All environment variables validated successfully!"
```

---

## Troubleshooting

### Issue: "OpenAI API key not configured"
**Solution:** Set `OPENAI_API_KEY` environment variable

### Issue: "Database connection failed"
**Solution:**
- Check `DATABASE_URL` format
- Verify database is running
- Check network connectivity
- Verify credentials

### Issue: "CORS error in frontend"
**Solution:**
- Verify `FRONTEND_URL` matches exactly
- Check protocol (http vs https)
- Verify port number

### Issue: "JWT token invalid"
**Solution:**
- Verify `JWT_SECRET_KEY` matches across all backend instances
- Check `JWT_ALGORITHM` setting
- Clear browser cookies/localStorage

### Issue: "OpenAI rate limit exceeded"
**Solution:**
- Reduce `RATE_LIMIT_CANCELLATION_RESEARCH`
- Check OpenAI dashboard for usage
- Verify caching is working
- Consider increasing OpenAI tier

---

## Reference

### Environment Variable Checklist

**Backend - Required:**
- [ ] `DATABASE_URL`
- [ ] `JWT_SECRET_KEY`
- [ ] `OPENAI_API_KEY` (for cancellation feature)
- [ ] `FRONTEND_URL`

**Backend - Optional:**
- [ ] `JWT_ALGORITHM`
- [ ] `OPENAI_MODEL`
- [ ] `CANCELLATION_CACHE_DAYS`
- [ ] `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`
- [ ] `REDIS_URL`
- [ ] `LOG_LEVEL`
- [ ] `SENTRY_DSN`

**Frontend - Required:**
- [ ] `VITE_API_URL`

**Frontend - Optional:**
- [ ] `VITE_APP_NAME`
- [ ] `VITE_ENABLE_ANALYTICS`

---

**Version:** 1.0.0
**Last Updated:** January 2025
**Maintained By:** Subscription Tracker Team
