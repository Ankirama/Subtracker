# Email Processing Pipeline

> End-to-end flow: mailbox connection → fetch → classify → extract → dedup → confidence routing → persistence. Implemented as a Celery task that wraps a provider-agnostic interface.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (React)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Dashboard │  │Settings  │  │Email Mgmt│  │Analytics │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST + WebSocket (progress)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Auth      │  │Subscrip. │  │Email Sync│  │Analytics │   │
│  │Endpoints │  │Endpoints │  │Endpoints │  │Endpoints │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────┬────────────────────┬──────────────────────────────┘
         │                    │
         │                    ▼
         │         ┌─────────────────────┐
         │         │   Celery Workers    │
         │         │  ┌──────────────┐   │
         │         │  │Email Importer│   │
         │         │  ├──────────────┤   │
         │         │  │AI Classifier │   │
         │         │  ├──────────────┤   │
         │         │  │AI Extractor  │   │
         │         │  ├──────────────┤   │
         │         │  │Deduplicator  │   │
         │         │  └──────────────┘   │
         │         └──────────┬──────────┘
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────┐
│         PostgreSQL Database              │
│  ┌────────┐ ┌────────┐ ┌────────┐      │
│  │Users   │ │Subscrip│ │Emails  │      │
│  ├────────┤ ├────────┤ ├────────┤      │
│  │Mailbox │ │Process │ │AI Logs │      │
│  └────────┘ └────────┘ └────────┘      │
└─────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌──────────────┐    ┌──────────────┐
│    Redis     │    │OpenAI API    │
│ (Cache/Queue)│    │(GPT-4o-mini) │
└──────────────┘    └──────────────┘
```

## Pipeline Flow

```
User triggers import/sync
         │
         ▼
┌─────────────────────┐
│ Celery Task: Import │
│ - Fetch batch (100) │
│ - Update progress   │
└──────────┬──────────┘
           ▼
┌─────────────────────────────┐
│ Email Provider Interface    │
│ (JMAP/Gmail/Outlook)        │
│ - Fetch emails by criteria │
│ - Return standardized format│
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ Stage 1: Classification     │
│ ┌─────────────────────────┐ │
│ │ Regex/Template Check    │ │
│ │ Known: netflix.com,     │ │
│ │        spotify.com, etc.│ │
│ └────────┬────────────────┘ │
│          │ No match          │
│          ▼                   │
│ ┌─────────────────────────┐ │
│ │ AI Classification       │ │
│ │ "Is subscription email?"│ │
│ │ Returns: Yes/No + conf% │ │
│ └────────┬────────────────┘ │
└──────────┼──────────────────┘
           │ Yes (>50%)
           ▼
┌─────────────────────────────┐
│ Stage 2: Extraction         │
│ ┌─────────────────────────┐ │
│ │ Template Extraction     │ │
│ │ (if known provider)     │ │
│ └────────┬────────────────┘ │
│          │ Or                │
│          ▼                   │
│ ┌─────────────────────────┐ │
│ │ AI Extraction           │ │
│ │ Extract: provider, $,   │ │
│ │          cycle, date    │ │
│ │ Returns: structured data│ │
│ └────────┬────────────────┘ │
└──────────┼──────────────────┘
           ▼
┌─────────────────────────────┐
│ Deduplication Logic         │
│ - Email sender patterns     │
│ - Provider + amount match   │
│ - Subscription ID detection │
│ - Time-based grouping       │
│ - PayPal→Twitch resolution  │
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ Confidence Routing          │
│ >85%  → Auto-accept         │
│ 50-84%→ Manual review       │
│ <50%  → Rejected (reviewable)│
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ Save to Database            │
│ - Subscription record       │
│ - Email reference (ID)      │
│ - Processing metadata       │
│ - Validation reasoning      │
└─────────────────────────────┘
```

The classify/extract internals are documented in ai-strategy.md; the dedup logic in deduplication.md. This file covers the orchestration: provider abstraction, the Celery task that drives it, and the email processor service that owns the per-email state machine.

## Email Provider Interface

All providers implement the same abstract interface so the pipeline is provider-agnostic. Phase 1 ships JMAP (Fastmail). Gmail OAuth and Outlook OAuth land in Phase 2.

```python
# backend/app/email_providers/base.py
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class EmailMessage(BaseModel):
    """Standardized email message format"""
    id: str  # Provider-specific ID
    subject: str
    sender: str
    recipient: str
    date: datetime
    body_html: Optional[str]
    body_text: Optional[str]
    headers: dict

class EmailFilter(BaseModel):
    """Filter criteria for fetching emails"""
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    sender: Optional[str]
    subject_contains: Optional[str]
    limit: int = 100
    offset: int = 0

class EmailProviderInterface(ABC):
    """Base interface all email providers must implement"""

    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """Authenticate with email provider"""
        pass

    @abstractmethod
    async def test_connection(self) -> dict:
        """Test connection and return status"""
        pass

    @abstractmethod
    async def fetch_emails(self, filter: EmailFilter) -> List[EmailMessage]:
        """Fetch emails matching filter criteria"""
        pass

    @abstractmethod
    async def get_email_by_id(self, email_id: str) -> EmailMessage:
        """Fetch specific email by ID"""
        pass

    @abstractmethod
    async def get_total_count(self, filter: Optional[EmailFilter] = None) -> int:
        """Get total number of emails matching filter"""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token"""
        pass
```

### JMAP Implementation (Phase 1)

```python
# backend/app/email_providers/jmap_provider.py
import httpx
from .base import EmailProviderInterface, EmailMessage, EmailFilter

class JMAPProvider(EmailProviderInterface):
    def __init__(self, jmap_url: str, access_token: str):
        self.jmap_url = jmap_url
        self.access_token = access_token
        self.client = httpx.AsyncClient()

    async def authenticate(self, credentials: dict) -> bool:
        # Implement JMAP authentication
        pass

    async def test_connection(self) -> dict:
        try:
            response = await self.client.post(
                self.jmap_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                    "methodCalls": [
                        ["Mailbox/query", {}, "0"]
                    ]
                }
            )
            response.raise_for_status()
            return {"status": "success", "message": "Connected successfully"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def fetch_emails(self, filter: EmailFilter) -> List[EmailMessage]:
        # Implement JMAP email fetching with filters
        # Use Email/query and Email/get methods
        pass

    async def get_email_by_id(self, email_id: str) -> EmailMessage:
        # Implement JMAP email fetch by ID
        pass

    async def get_total_count(self, filter: Optional[EmailFilter] = None) -> int:
        # Use JMAP Email/query with limit=0 to get count
        pass

    async def refresh_token(self, refresh_token: str) -> dict:
        # Implement JMAP token refresh
        pass
```

### Provider Factory

```python
# backend/app/email_providers/factory.py
from .jmap_provider import JMAPProvider
# Future: from .gmail_provider import GmailProvider

def create_email_provider(provider_type: str, credentials: dict):
    """Factory to create email provider instances"""

    providers = {
        "jmap": JMAPProvider,
        # "gmail": GmailProvider,
        # "outlook": OutlookProvider,
    }

    if provider_type not in providers:
        raise ValueError(f"Unsupported provider type: {provider_type}")

    return providers[provider_type](**credentials)
```

JMAP uses provider-specific email IDs — do not assume any format. HTML emails are parsed with BeautifulSoup. French date formats are handled by the AI extraction layer.

## Celery Task Architecture

Imports and re-syncs run as Celery tasks. Progress is written back to `processing_jobs` so the frontend can poll or stream updates.

### Import Task

```python
# backend/app/tasks/email_import.py
from celery import Task, group, chain
from app.celery_app import celery_app
from app.email_providers.factory import create_email_provider
from app.services.email_processor import EmailProcessor

class ImportTask(Task):
    """Base task with progress tracking"""

    def update_progress(self, job_id, **kwargs):
        from app.models import ProcessingJob
        job = ProcessingJob.query.get(job_id)
        for key, value in kwargs.items():
            setattr(job, key, value)
        job.save()

@celery_app.task(base=ImportTask, bind=True)
def import_emails_task(self, job_id: str, mailbox_id: str, config: dict):
    """Main import task"""

    # Get mailbox and create provider
    mailbox = Mailbox.query.get(mailbox_id)
    provider = create_email_provider(
        mailbox.provider_type,
        decrypt_credentials(mailbox.encrypted_credentials)
    )

    # Get total count
    total_emails = await provider.get_total_count(
        EmailFilter(**config.get('filter', {}))
    )

    self.update_progress(job_id, total_emails=total_emails, status='processing')

    # Process in batches
    batch_size = config.get('batch_size', 100)
    processor = EmailProcessor(mailbox.user_id, mailbox_id)

    processed = 0
    for offset in range(0, total_emails, batch_size):
        # Fetch batch
        emails = await provider.fetch_emails(
            EmailFilter(
                **config.get('filter', {}),
                limit=batch_size,
                offset=offset
            )
        )

        # Process each email
        for email in emails:
            try:
                result = await processor.process_email(email)
                processed += 1

                # Update progress
                self.update_progress(
                    job_id,
                    processed_emails=processed,
                    accepted_count=processor.stats['accepted'],
                    rejected_count=processor.stats['rejected'],
                    pending_review_count=processor.stats['pending_review']
                )

            except Exception as e:
                logger.error(f"Error processing email {email.id}: {e}")

    self.update_progress(job_id, status='completed', completed_at=datetime.now())
    return {
        "processed": processed,
        "stats": processor.stats
    }
```

### Email Processor Service

The processor is the per-email state machine that ties classification, extraction, deduplication, and persistence together.

```python
# backend/app/services/email_processor.py
from app.services.ai_service import AIService
from app.services.template_matcher import TemplateMatcher
from app.services.deduplicator import Deduplicator

class EmailProcessor:
    def __init__(self, user_id: str, mailbox_id: str):
        self.user_id = user_id
        self.mailbox_id = mailbox_id
        self.ai_service = AIService()
        self.template_matcher = TemplateMatcher()
        self.deduplicator = Deduplicator(user_id)
        self.stats = {
            'accepted': 0,
            'rejected': 0,
            'pending_review': 0
        }

    async def process_email(self, email: EmailMessage):
        """Process single email through the pipeline"""

        # Stage 1: Classification
        is_subscription, confidence, method = await self.classify_email(email)

        if not is_subscription:
            return self.create_processing_record(
                email,
                status='rejected',
                confidence=confidence,
                reason="Not identified as subscription email"
            )

        # Stage 2: Extraction
        extracted_data = await self.extract_subscription_data(email, method)

        # Stage 3: Deduplication
        duplicates = self.deduplicator.find_duplicates(extracted_data)

        if duplicates:
            merged = self.deduplicator.auto_merge(extracted_data, duplicates[0])
            return self.create_processing_record(
                email,
                status='accepted',
                confidence=confidence,
                subscription_id=merged.id,
                reason="Merged with existing subscription"
            )

        # Stage 4: Confidence-based routing
        if confidence >= 85:
            # Auto-accept
            subscription = self.create_subscription(extracted_data, confidence)
            self.stats['accepted'] += 1
            return self.create_processing_record(
                email,
                status='accepted',
                confidence=confidence,
                subscription_id=subscription.id
            )
        elif confidence >= 50:
            # Manual review
            self.stats['pending_review'] += 1
            return self.create_processing_record(
                email,
                status='pending_review',
                confidence=confidence,
                extracted_data=extracted_data
            )
        else:
            # Rejected
            self.stats['rejected'] += 1
            return self.create_processing_record(
                email,
                status='rejected',
                confidence=confidence,
                reason=f"Low confidence ({confidence}%)"
            )

    async def classify_email(self, email: EmailMessage):
        """Stage 1: Classify if email is subscription-related"""

        # Try template matching first
        template_match = self.template_matcher.find_match(email)
        if template_match:
            return True, 100.0, f"template_{template_match.provider}"

        # Fall back to AI
        result = await self.ai_service.classify_email(email)
        return result.is_subscription, result.confidence, "ai_classification"

    async def extract_subscription_data(self, email: EmailMessage, method: str):
        """Stage 2: Extract subscription data"""

        if method.startswith("template_"):
            provider = method.replace("template_", "")
            return self.template_matcher.extract(email, provider)

        return await self.ai_service.extract_subscription_data(email)
```

## Tests

```python
# backend/tests/test_email_processor.py
import pytest
from app.services.email_processor import EmailProcessor

@pytest.mark.asyncio
async def test_classify_known_provider():
    processor = EmailProcessor(user_id="test", mailbox_id="test")
    email = EmailMessage(
        id="test",
        subject="Your Netflix Receipt",
        sender="info@netflix.com",
        date=datetime.now(),
        body_text="Your monthly subscription of $15.99"
    )

    is_sub, confidence, method = await processor.classify_email(email)
    assert is_sub == True
    assert confidence == 100.0
    assert method == "template_netflix"
```

(See deduplication.md for the dedup test.)

## Reference Material from TECHNICAL_SPEC.md

This section preserves content from `TECHNICAL_SPEC.md` whose primary subject was the architecture as a whole rather than a specific architectural domain. Batch 10 (`docs/architecture/overview.md`) will absorb most of it; until then, it lives here so nothing is lost.

<!-- reconcile manually: content below should move to docs/architecture/overview.md when that file is authored. -->

### Executive Summary (from TECHNICAL_SPEC.md)

A multi-user SaaS web application that automatically discovers and tracks subscriptions by analyzing emails from connected mailboxes using AI-powered extraction, supporting JMAP (with extensibility for Gmail/Outlook OAuth).

### Tech Stack (from TECHNICAL_SPEC.md §1)

**Frontend**
- Framework: React 18+ with TypeScript
- UI Library: Chakra UI
- State Management: React Query + Context API
- Charts: Recharts
- Build Tool: Vite
- HTTP Client: Axios

**Backend**
- Framework: FastAPI (Python 3.11+)
- ORM: SQLAlchemy 2.0
- Validation: Pydantic v2
- Migrations: Alembic
- Task Queue: Celery 5+
- Broker/Cache: Redis 7+
- ASGI Server: Uvicorn

**Database**
- Primary DB: PostgreSQL 15+
- Features Used: JSONB, Full-text search, Triggers

**AI/LLM**
- Provider: OpenAI
- Model: GPT-4o-mini (configurable)
- Integration: OpenAI Assistants API
- Fallback: Direct API calls for simple extraction

**Email Integration**
- Primary: JMAP (Fastmail)
- Architecture: Unified provider interface
- Future: Gmail OAuth, Outlook OAuth, IMAP

**DevOps**
- Containerization: Docker + Docker Compose
- Reverse Proxy: Nginx (optional for production)
- Environment: Separate dev/prod configurations

### Appendix A: Technology Choices Rationale (from TECHNICAL_SPEC.md)

**FastAPI vs Django/Flask:**
- FastAPI: Modern, async, automatic OpenAPI docs, Pydantic validation
- Better for API-first architecture with real-time features

**React Query vs Redux:**
- React Query: Better for server-state management, automatic caching, less boilerplate
- Context API sufficient for minimal client-state (auth, settings)

**Celery vs alternatives:**
- Celery: Mature, robust, good monitoring tools (Flower)
- Redis broker: Fast, simple, works well for our scale

**PostgreSQL vs MongoDB:**
- PostgreSQL: Structured data, ACID compliance, powerful querying
- JSONB for flexible fields (extracted_data, payment_processor)

**Chakra UI vs Material-UI:**
- Chakra: Modern, accessible by default, TypeScript support, easier theming
- Good component library without being opinionated

### Appendix B: Open Questions (from TECHNICAL_SPEC.md)

1. **Email retention**: How long to keep email processing records?
2. **AI costs**: Budget for OpenAI API usage at scale?
3. **Backup strategy**: Frequency and retention for database backups?
4. **Production hosting**: Cloud provider preference (AWS, GCP, Azure, DigitalOcean)?
5. **Domain name**: What domain for production deployment?

### Phase Roadmap and Next Steps (from TECHNICAL_SPEC.md §12, §15)

The original 4-phase roadmap and the week-by-week implementation plan are preserved in `docs/roadmap/current.md` and `docs/_archive/roadmap-phase-1-completed.md`. Selected highlights kept here for architectural context:

- **Phase 1 (MVP, Months 1–2)**: JMAP integration, GPT-4o-mini classification & extraction, template matching for 5–10 common providers, confidence-based routing, manual review interface, basic deduplication, data export, basic analytics (spending trends, category breakdown, top expensive).
- **Phase 2 (Enhanced, Months 3–4)**: Gmail / Outlook OAuth, multiple mailboxes per user, configurable sync, template builder UI, learning from user feedback, budget tracking and alerts, spending forecasting, advanced filtering and bulk ops.
- **Phase 3 (AI Excellence, Months 5–6)**: AI-assisted template generation, fine-tuning on feedback, anomaly detection, smart categorization, subscription sharing, public API, browser extension, mobile app.
- **Phase 4 (Scale & Polish, Months 7–8)**: Query optimization, caching, GDPR / SOC 2, 2FA, production Docker setup, CI/CD, monitoring (Sentry, Datadog), monetization (Stripe + free tier).

### Setup, Docker, and Development Workflow (from TECHNICAL_SPEC.md §9, §11)

Setup and ad-hoc operational commands now live in `docs/setup.md` and `docs/operations/deployment.md`. The original `docker-compose.dev.yml` snippet, Dockerfiles, and `.env.example` from `TECHNICAL_SPEC.md` overlap with those files; consult them for the canonical version. The frontend project structure and React Query hook patterns are recorded in `api-conventions.md`.
