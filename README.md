# Subscription Tracker

An intelligent subscription management platform that automatically discovers and tracks your subscriptions by analyzing emails using AI.

## Features

- 📧 **Email Integration** - Connect multiple mailboxes (JMAP, Gmail, Outlook)
- 🤖 **AI-Powered Detection** - Automatic subscription discovery using GPT-4o-mini
- 🌍 **Multi-Language** - Support for French and English emails
- 📊 **Analytics Dashboard** - Track spending trends, categories, and budgets
- ✅ **Smart Review** - Confidence-based routing with manual review workflow
- 🔍 **Intelligent Deduplication** - Merge duplicate subscriptions automatically

## Tech Stack

- **Frontend**: React + TypeScript + Chakra UI + React Query
- **Backend**: FastAPI + PostgreSQL + SQLAlchemy
- **Jobs**: Celery + Redis
- **AI**: OpenAI GPT-4o-mini
- **DevOps**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key
- (Optional) Fastmail or other JMAP-compatible email account for testing

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd subscription_tracker
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Generate encryption key**
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Add the output to `.env` as `ENCRYPTION_KEY`

4. **Configure environment variables**
   Edit `.env` and add:
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `JWT_SECRET_KEY` - Random secret (use `openssl rand -hex 32`)
   - `ENCRYPTION_KEY` - From step 3

5. **Start the application**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

6. **Run database migrations**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

7. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Development

### Common Commands

```bash
# View logs
docker-compose -f docker-compose.dev.yml logs -f backend
docker-compose -f docker-compose.dev.yml logs -f celery_worker

# Restart a service
docker-compose -f docker-compose.dev.yml restart backend

# Run tests
docker-compose exec backend pytest
docker-compose exec frontend npm test

# Access database
docker-compose exec postgres psql -U postgres -d subscription_tracker

# Stop all services
docker-compose -f docker-compose.dev.yml down
```

### Project Structure

```
subscription_tracker/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # Route handlers
│   │   ├── models/      # Database models
│   │   ├── services/    # Business logic
│   │   ├── tasks/       # Celery tasks
│   │   └── security/    # Auth & encryption
│   └── tests/           # Backend tests
├── frontend/            # React frontend
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── hooks/       # Custom hooks
│   │   ├── api/         # API clients
│   │   └── types/       # TypeScript types
│   └── tests/           # Frontend tests
├── docker-compose.dev.yml
├── docs/architecture/overview.md   # Detailed technical documentation
└── CLAUDE.md           # Guide for AI assistants
```

## Documentation

- **[Technical Specification](docs/architecture/overview.md)** - Complete architecture and API documentation
- **[CLAUDE.md](CLAUDE.md)** - Development guide for AI assistants
- **[API Documentation](http://localhost:8000/docs)** - Interactive OpenAPI docs (when running)

## Architecture Overview

### Email Processing Pipeline

```
Email Provider → Batch Fetch (100) →
Classification (Template/AI) →
Extraction (Template/AI) →
Deduplication →
Confidence Routing →
Database
```

### Confidence Thresholds

- **≥85%**: Auto-accept and create subscription
- **50-84%**: Manual review required
- **<50%**: Rejected (can be manually reviewed)

### AI Strategy

- **Two-stage processing**: First classify (is it a subscription?), then extract details
- **Hybrid approach**: Template matching for known providers, AI for unknowns
- **Learning system**: User corrections stored as training examples
- **Multi-language**: Handles French and English emails

## Development Roadmap

### Phase 1: MVP (Current)
- ✅ User authentication
- ✅ JMAP email integration
- ✅ AI classification and extraction
- ✅ Basic dashboard with analytics
- ✅ Manual review interface
- 🔄 Template matching for common providers

### Phase 2: Enhanced Features
- Gmail/Outlook OAuth integration
- Template builder UI
- Budget tracking and alerts
- Advanced analytics

### Phase 3: AI Excellence
- Fine-tuning and learning improvements
- Smart suggestions and optimization
- Renewal reminders

### Phase 4: Production Ready
- Performance optimization
- Full GDPR compliance
- CI/CD pipeline
- Monitoring and alerting

## Security

- **Password Storage**: bcrypt hashing with automatic salts
- **Authentication**: JWT tokens (access + refresh)
- **Credential Encryption**: Fernet symmetric encryption for email credentials
- **Data Isolation**: Application-level user filtering
- **CORS**: Configured for localhost development

## Environment Variables

Required environment variables:

```bash
# Database
DATABASE_URL=postgresql://postgres:devpassword@postgres:5432/subscription_tracker

# Redis
REDIS_URL=redis://redis:6379/0

# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Security
JWT_SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# CORS
CORS_ORIGINS=http://localhost:5173
```

## Troubleshooting

**Services won't start**
- Ensure Docker is running
- Check if ports 5173, 8000, 5432, 6379 are available
- Run `docker-compose -f docker-compose.dev.yml down` and try again

**Database connection errors**
- Wait for PostgreSQL to be healthy: `docker-compose ps`
- Check logs: `docker-compose logs postgres`

**Migration errors**
- Check migration status: `docker-compose exec backend alembic current`
- Reset database (⚠️ loses data): `docker-compose down -v && docker-compose up -d`

**Frontend not loading**
- Check backend is running: `curl http://localhost:8000/health`
- Clear browser cache
- Check frontend logs: `docker-compose logs frontend`

## Contributing

This is currently a personal project. More information about contributing will be added in future phases.

## License

[To be determined]

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [OpenAI](https://openai.com/)
- UI components from [Chakra UI](https://chakra-ui.com/)
# CI/CD Pipeline Active
