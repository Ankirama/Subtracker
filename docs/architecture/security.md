# Security

> Application-level security model: multi-tenancy, CORS, monitoring/logging hooks, and the rationale for deferring PostgreSQL RLS. For authentication-specific topics (JWT, password hashing, credential encryption) see `auth.md`.

## Multi-Tenancy Model

Phase 1 enforces tenant isolation at the **application layer**. Every query that touches user-scoped data filters by `user_id`. There is no PostgreSQL row-level security (RLS) yet.

**Why application-level rather than RLS:**
- Simpler to implement and debug.
- Easier to audit and test.
- Defense-in-depth via RLS is on the Phase 4 roadmap.

This means a missing `user_id` filter is a security bug, not just a data-correctness bug. Code review and tests must specifically verify that every endpoint and every service method filters by the authenticated user.

**Other application-level rules:**
- Encrypted credentials must be decrypted only inside the request/task lifecycle that needs them — never logged, never returned to the client.
- Cross-tenant references (e.g. `subscriptions.mailbox_id`) are validated against the same `user_id` before being persisted.

## CORS Configuration

CORS is configured for the dev origin (`http://localhost:5173`) and accepts a comma-separated list via the `CORS_ORIGINS` env var.

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS setup for development
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Production origins are added via the same env var; the application code does not need to change.

## Secrets and Environment Variables

All secrets are sourced from environment variables — never committed.

Required:
- `JWT_SECRET_KEY` — for JWT signing. Generate via `openssl rand -hex 32`.
- `ENCRYPTION_KEY` — Fernet key for mailbox credential encryption. Generate via:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `DATABASE_URL` — PostgreSQL connection string.
- `REDIS_URL` — broker/cache.
- `OPENAI_API_KEY` — used by the AI service.
- `CORS_ORIGINS` — comma-separated allowed origins.

Rotation guidance: rotating `JWT_SECRET_KEY` invalidates all live tokens (forced re-login). Rotating `ENCRYPTION_KEY` requires re-encrypting every `mailboxes.encrypted_credentials` row; do this only via a deliberate migration.

## Logging and Error Tracking

### Application Logging

```python
# backend/app/logging_config.py
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log')
        ]
    )

    # Set levels for specific loggers
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('celery').setLevel(logging.INFO)
```

Log every error with context (`user_id`, `email_id`, `job_id`, etc.). User-facing error responses include a `detail` message but never internal stack traces.

### Error Tracking (Future: Sentry)

```python
# backend/app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
    )
```

Sentry integration is gated on `SENTRY_DSN`; production deploys (Phase 4) set it.

## Roadmap

Defense-in-depth additions deferred to Phase 4:
- PostgreSQL row-level security (RLS) policies as a second line of tenant isolation.
- Two-factor authentication.
- Full GDPR compliance and SOC 2 preparation.
- Advanced audit logging.
- Rate limiting on auth and import endpoints.
