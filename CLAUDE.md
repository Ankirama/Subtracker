# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Subscription Tracker** - A multi-user SaaS web application that automatically discovers and tracks subscriptions by analyzing emails from connected mailboxes using AI-powered extraction.

**Key Features:**
- Email integration (JMAP/Gmail/Outlook OAuth)
- AI-powered subscription detection and extraction
- Multi-language support (French/English)
- Intelligent deduplication
- Budget tracking and spending analytics
- Confidence-based routing with manual review

## Tech Stack

**Frontend:**
- React 18+ with TypeScript
- Chakra UI for components
- React Query + Context API for state
- Recharts for analytics
- Vite for build tooling

**Backend:**
- Python 3.11+ with FastAPI
- SQLAlchemy 2.0 ORM
- PostgreSQL 15+ database
- Celery 5+ for background jobs
- Redis for broker/cache
- OpenAI GPT-4o-mini for AI extraction

**DevOps:**
- Docker Compose for development
- Separate dev/prod configurations
- Hot-reload enabled for development

## Development Commands

### Initial Setup
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Generate encryption key for credentials
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env as ENCRYPTION_KEY

# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Run database migrations
docker-compose exec backend alembic upgrade head

# Access application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Common Commands
```bash
# View logs
docker-compose -f docker-compose.dev.yml logs -f backend
docker-compose -f docker-compose.dev.yml logs -f celery_worker

# Restart a service (triggers hot-reload)
docker-compose -f docker-compose.dev.yml restart backend

# Database migrations
docker-compose exec backend alembic revision --autogenerate -m "description"
docker-compose exec backend alembic upgrade head
docker-compose exec backend alembic downgrade -1

# Access database
docker-compose exec postgres psql -U postgres -d subscription_tracker

# Run tests
docker-compose exec backend pytest
docker-compose exec frontend npm test

# Install dependencies
docker-compose exec backend pip install <package>
# Then update backend/requirements.txt
docker-compose exec frontend npm install <package>
```

## Architecture Overview

### Email Processing Pipeline
```
User connects mailbox → Fetch emails in batches (100) →
Stage 1: Classification (Template/AI) →
Stage 2: Extraction (Template/AI) →
Stage 3: Deduplication →
Confidence Routing (>85% auto-accept, 50-84% review, <50% reject) →
Save to database
```

### Background Job Flow
- Celery workers process email imports asynchronously
- Progress tracked via WebSocket for real-time UI updates
- Jobs stored in `processing_jobs` table with status tracking

### AI Strategy
- **OpenAI Assistant** for classification and extraction
- **Template matching** for known providers (higher confidence)
- **Two-stage processing**: Classify first, then extract
- **Confidence thresholds**: Configurable per user (default 85%/50%)
- **Learning**: Store user corrections as training examples

### Deduplication Logic
Multi-factor scoring:
- Email sender similarity (30 points)
- Provider name fuzzy match (40 points)
- Amount similarity within 5% (20 points)
- Billing cycle match (10 points)
- Same billing period (10 points)
- Special handling: PayPal→Actual Provider resolution

Threshold: 70+ points = duplicate (auto-merge)

## Key Database Tables

**Core Tables:**
- `users` - User accounts with bcrypt password hashing
- `mailboxes` - Email account connections (encrypted credentials)
- `subscriptions` - Detected subscriptions with metadata
- `email_processing_records` - Email analysis results and references
- `processing_jobs` - Background job tracking
- `budgets` - Overall and per-category spending limits

**Important Fields:**
- `subscriptions.custom_label` - For differentiating same-provider subs (e.g., Twitch streamers)
- `subscriptions.payment_processor` - JSONB for PayPal→Service mapping
- `subscriptions.confidence_score` - AI extraction confidence (0-100)
- `email_processing_records.email_id` - Provider-specific ID for re-fetching
- `email_processing_records.extracted_data` - JSONB with raw extraction results

## Email Provider Interface

All email providers implement `EmailProviderInterface`:
```python
- authenticate(credentials) -> bool
- test_connection() -> dict
- fetch_emails(filter) -> List[EmailMessage]
- get_email_by_id(email_id) -> EmailMessage
- get_total_count(filter) -> int
- refresh_token(refresh_token) -> dict
```

**Current Implementations:**
- JMAP (Fastmail) - Phase 1
- Gmail OAuth - Phase 2
- Outlook OAuth - Phase 2

**Factory Pattern:**
```python
provider = create_email_provider(provider_type, credentials)
```

## Security Implementation

**Password Storage:**
- bcrypt hashing with automatic salt generation
- Never store plaintext passwords

**JWT Authentication:**
- Access tokens (30 min expiry)
- Refresh tokens (7 day expiry)
- Bearer token in Authorization header

**Credential Encryption:**
- Fernet symmetric encryption for mailbox credentials
- Store encrypted access/refresh tokens
- Encryption key from environment variable

**Application-Level Security:**
- User isolation via `user_id` filters in queries
- No PostgreSQL RLS (simpler for now)
- CORS configured for localhost development

## Code Organization Patterns

### Backend Structure
```
backend/
├── app/
│   ├── api/              # FastAPI route handlers
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic (EmailProcessor, AIService, etc.)
│   ├── tasks/            # Celery tasks
│   ├── email_providers/  # Provider interface and implementations
│   ├── security/         # Auth, encryption, JWT
│   └── main.py           # FastAPI app initialization
├── alembic/              # Database migrations
└── tests/                # Pytest tests
```

### Frontend Structure
```
frontend/
├── src/
│   ├── components/       # Organized by feature (auth, subscriptions, etc.)
│   ├── hooks/            # Custom React hooks (useSubscriptions, etc.)
│   ├── contexts/         # React contexts (Auth, Settings)
│   ├── api/              # API client functions
│   ├── types/            # TypeScript type definitions
│   └── utils/            # Helper functions
```

## Important Conventions

**API Patterns:**
- All endpoints prefixed with `/api/`
- RESTful resource naming
- Consistent error responses with detail messages
- Pagination for list endpoints (page, page_size)

**Database Conventions:**
- UUID primary keys for all tables
- `created_at` and `updated_at` timestamps on most tables
- Soft deletes via `is_active` boolean (where applicable)
- JSONB for flexible/structured metadata fields

**Testing:**
- Backend: pytest with async support
- Frontend: React Testing Library
- E2E: Playwright (future phase)

**Error Handling:**
- Log all errors with context (user_id, email_id, etc.)
- User-friendly error messages in responses
- Sentry integration for production (Phase 4)

## Phase Roadmap Context

**Current Phase: Phase 1 (MVP)**
Focus areas:
- Core email import functionality
- Basic AI classification/extraction
- Template matching for 5-10 common providers
- Essential dashboard with 3 charts
- Manual review interface

**Not Yet Implemented:**
- Gmail/Outlook OAuth (Phase 2)
- Template builder UI (Phase 2)
- Advanced budget alerts (Phase 2)
- Mobile app (Phase 3)
- Production deployment (Phase 4)

## Critical Design Decisions

**Why OpenAI Assistant over direct API?**
- Maintains conversation context for iterative extraction
- Can use function calling for structured output
- Easier to update instructions without code changes
- Fallback to direct API calls if needed

**Why Celery over simpler alternatives?**
- Mature ecosystem with monitoring (Flower)
- Robust retry and error handling
- Beat scheduler for periodic syncs
- Scales horizontally when needed

**Why single custom_label field vs flexible JSONB?**
- MVP simplicity - most users need one differentiator
- Can migrate to JSONB in Phase 2 if needed
- Easier to query and index

**Why application-level filtering vs PostgreSQL RLS?**
- Simpler to implement and debug
- Easier to audit and test
- Can add RLS in Phase 4 for defense-in-depth

## Configuration Notes

**Environment Variables Required:**
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - OpenAI API key
- `JWT_SECRET_KEY` - For JWT signing (generate random)
- `ENCRYPTION_KEY` - Fernet key for credential encryption
- `CORS_ORIGINS` - Comma-separated allowed origins

**OpenAI Assistant Setup:**
- Create assistant via API or dashboard
- Store assistant ID in environment or database
- Configure with subscription extraction instructions
- Model: gpt-4o-mini (configurable per user)

## Common Gotchas

**Email Processing:**
- JMAP uses special email IDs - don't assume format
- HTML emails need BeautifulSoup parsing
- French date formats differ - AI handles this
- PayPal emails need special duplicate handling

**Database:**
- Always filter by `user_id` for multi-tenancy
- Encrypted credentials must be decrypted before use
- JSONB fields need explicit casting in raw SQL

**Docker:**
- Volume mounts enable hot-reload
- Database persists in named volume `postgres_data`
- Restart backend container to pick up new dependencies

**Frontend:**
- React Query caches for 30 seconds by default
- WebSocket reconnection logic needed for job progress
- Chakra UI requires ThemeProvider wrapper

## Useful SQL Queries

```sql
-- Find subscriptions pending review
SELECT * FROM email_processing_records
WHERE processing_status = 'pending_review'
AND user_id = 'user-uuid'
ORDER BY processed_at DESC;

-- User spending summary
SELECT category, SUM(amount) as total, COUNT(*) as count
FROM subscriptions
WHERE user_id = 'user-uuid' AND is_active = true
GROUP BY category;

-- Failed processing jobs
SELECT * FROM processing_jobs
WHERE status = 'failed'
ORDER BY created_at DESC;
```

## Documentation References

- **Full Technical Spec**: `TECHNICAL_SPEC.md` - Complete architecture and API documentation
- **API Documentation**: `http://localhost:8000/docs` - Interactive OpenAPI docs
- **Database Schema**: See `backend/alembic/versions/` for migration history

## Support and Troubleshooting

**Common Issues:**
- "Connection refused" → Ensure Docker services are running
- "OPENAI_API_KEY not found" → Check .env file
- "Migration conflict" → Run `alembic heads` to check state
- "Port already in use" → Check for other running services on 5173/8000

**Debugging:**
- Backend logs: `docker-compose logs -f backend`
- Celery logs: `docker-compose logs -f celery_worker`
- Database logs: `docker-compose logs -f postgres`
- Frontend console: Browser DevTools

For detailed architecture decisions and rationale, see `TECHNICAL_SPEC.md`.
