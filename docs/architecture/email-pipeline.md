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
