# Technical Specification: Email-Based Subscription Tracker

## Executive Summary

A multi-user SaaS web application that automatically discovers and tracks subscriptions by analyzing emails from connected mailboxes using AI-powered extraction, supporting JMAP (with extensibility for Gmail/Outlook OAuth).

---

## 1. Tech Stack

### Frontend
- **Framework**: React 18+ with TypeScript
- **UI Library**: Chakra UI
- **State Management**: React Query + Context API
- **Charts**: Recharts
- **Build Tool**: Vite
- **HTTP Client**: Axios

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **ORM**: SQLAlchemy 2.0
- **Validation**: Pydantic v2
- **Migrations**: Alembic
- **Task Queue**: Celery 5+
- **Broker/Cache**: Redis 7+
- **ASGI Server**: Uvicorn

### Database
- **Primary DB**: PostgreSQL 15+
- **Features Used**: JSONB, Full-text search, Triggers

### AI/LLM
- **Provider**: OpenAI
- **Model**: GPT-4o-mini (configurable)
- **Integration**: OpenAI Assistants API
- **Fallback**: Direct API calls for simple extraction

### Email Integration
- **Primary**: JMAP (Fastmail)
- **Architecture**: Unified provider interface
- **Future**: Gmail OAuth, Outlook OAuth, IMAP

### DevOps
- **Containerization**: Docker + Docker Compose
- **Reverse Proxy**: Nginx (optional for production)
- **Environment**: Separate dev/prod configurations

---

## 2. System Architecture

### High-Level Architecture

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

### Email Processing Pipeline

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

---

## 3. Database Schema

### 3.1 Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt
    salt VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    settings JSONB DEFAULT '{}'::jsonb  -- User preferences
);

CREATE INDEX idx_users_email ON users(email);
```

### 3.2 Mailboxes Table
```sql
CREATE TABLE mailboxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider_type VARCHAR(50) NOT NULL,  -- 'jmap', 'gmail', 'outlook'
    email_address VARCHAR(255) NOT NULL,

    -- Encrypted credentials (using cryptography lib)
    encrypted_credentials TEXT NOT NULL,  -- JSON with access/refresh tokens

    display_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMP,
    last_sync_status VARCHAR(50),  -- 'success', 'failed', 'in_progress'

    -- Sync configuration
    sync_frequency VARCHAR(50) DEFAULT 'weekly',  -- 'manual', 'daily', 'weekly'
    batch_size INTEGER DEFAULT 100,
    import_date_filter VARCHAR(50),  -- 'all', '1year', '2years', etc.

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id, email_address)
);

CREATE INDEX idx_mailboxes_user ON mailboxes(user_id);
CREATE INDEX idx_mailboxes_active ON mailboxes(is_active);
```

### 3.3 Subscriptions Table
```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mailbox_id UUID REFERENCES mailboxes(id) ON DELETE SET NULL,

    -- Core subscription data
    provider VARCHAR(255) NOT NULL,
    email_sender VARCHAR(255),
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    billing_cycle VARCHAR(50) NOT NULL,  -- 'monthly', 'yearly', 'quarterly'

    renewal_date DATE,
    next_billing_date DATE,  -- Calculated field

    is_active BOOLEAN DEFAULT true,

    -- Categorization
    category VARCHAR(100),  -- 'streaming', 'software', 'utilities', etc.
    tags TEXT[],  -- Array of custom tags

    -- Custom differentiation field (e.g., "Streamer Name")
    custom_label VARCHAR(255),

    notes TEXT,

    -- Tracking
    first_detected_at TIMESTAMP DEFAULT NOW(),
    last_confirmed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Processing metadata
    confidence_score DECIMAL(5, 2),  -- 0.00 to 100.00
    extraction_method VARCHAR(50),  -- 'template', 'ai', 'manual'

    -- Payment processor metadata (for PayPal→Twitch cases)
    payment_processor JSONB,  -- {provider: 'paypal', email: 'service@paypal.com'}

    CONSTRAINT valid_confidence CHECK (confidence_score >= 0 AND confidence_score <= 100)
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_active ON subscriptions(is_active);
CREATE INDEX idx_subscriptions_category ON subscriptions(category);
CREATE INDEX idx_subscriptions_provider ON subscriptions(provider);
CREATE INDEX idx_subscriptions_renewal ON subscriptions(renewal_date);
```

### 3.4 Subscription History Table
```sql
CREATE TABLE subscription_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,

    -- Track what changed
    field_changed VARCHAR(100) NOT NULL,  -- 'amount', 'billing_cycle', 'status'
    old_value TEXT,
    new_value TEXT,

    changed_at TIMESTAMP DEFAULT NOW(),
    changed_by VARCHAR(50) DEFAULT 'system',  -- 'system', 'user', 'ai'

    notes TEXT
);

CREATE INDEX idx_history_subscription ON subscription_history(subscription_id);
CREATE INDEX idx_history_date ON subscription_history(changed_at);
```

### 3.5 Email Processing Records Table
```sql
CREATE TABLE email_processing_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mailbox_id UUID NOT NULL REFERENCES mailboxes(id) ON DELETE CASCADE,

    -- Email identification (don't store full email)
    email_id VARCHAR(500) NOT NULL,  -- Provider-specific ID for re-fetching
    email_subject VARCHAR(500),
    email_sender VARCHAR(255),
    email_date TIMESTAMP,

    -- Processing results
    processing_status VARCHAR(50) NOT NULL,  -- 'accepted', 'rejected', 'pending_review', 'manually_added'
    classification_result BOOLEAN,  -- Is subscription email?
    classification_confidence DECIMAL(5, 2),

    -- Extracted data (even if rejected, for review)
    extracted_data JSONB,  -- Structured subscription data

    -- Linked subscription (if accepted)
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,

    -- Validation reasoning
    validation_reason TEXT,  -- Why accepted/rejected
    extraction_method VARCHAR(50),  -- 'template_netflix', 'ai_gpt4o_mini', 'manual'

    -- AI metadata
    ai_prompt_used TEXT,
    ai_response TEXT,
    ai_model VARCHAR(50),

    processed_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,  -- When user manually reviewed
    reviewed_by UUID REFERENCES users(id),

    UNIQUE(mailbox_id, email_id)
);

CREATE INDEX idx_email_proc_mailbox ON email_processing_records(mailbox_id);
CREATE INDEX idx_email_proc_status ON email_processing_records(processing_status);
CREATE INDEX idx_email_proc_subscription ON email_processing_records(subscription_id);
```

### 3.6 Budgets Table
```sql
CREATE TABLE budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    budget_type VARCHAR(50) NOT NULL,  -- 'overall', 'category'
    category VARCHAR(100),  -- NULL for overall budget

    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    period VARCHAR(50) NOT NULL DEFAULT 'monthly',  -- 'monthly', 'yearly'

    alert_threshold DECIMAL(5, 2) DEFAULT 90.00,  -- Alert at 90% of budget

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_category CHECK (
        (budget_type = 'overall' AND category IS NULL) OR
        (budget_type = 'category' AND category IS NOT NULL)
    ),
    UNIQUE(user_id, budget_type, category)
);

CREATE INDEX idx_budgets_user ON budgets(user_id);
```

### 3.7 Processing Jobs Table
```sql
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mailbox_id UUID NOT NULL REFERENCES mailboxes(id) ON DELETE CASCADE,

    job_type VARCHAR(50) NOT NULL,  -- 'import', 'sync', 'reprocess'
    status VARCHAR(50) NOT NULL,  -- 'queued', 'processing', 'completed', 'failed'

    -- Progress tracking
    total_emails INTEGER,
    processed_emails INTEGER DEFAULT 0,
    accepted_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    pending_review_count INTEGER DEFAULT 0,

    -- Job configuration
    config JSONB,  -- {batch_size, date_filter, etc.}

    -- Task tracking
    celery_task_id VARCHAR(255),

    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_jobs_user ON processing_jobs(user_id);
CREATE INDEX idx_jobs_status ON processing_jobs(status);
CREATE INDEX idx_jobs_celery ON processing_jobs(celery_task_id);
```

### 3.8 Templates Table (Phase 1: Hardcoded, Phase 2+: User-created)
```sql
CREATE TABLE email_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    provider_name VARCHAR(255) NOT NULL,
    template_type VARCHAR(50) NOT NULL,  -- 'regex', 'ai_assisted', 'hybrid'

    -- Pattern matching
    sender_pattern VARCHAR(500),  -- Regex for email sender
    subject_pattern VARCHAR(500),  -- Regex for subject

    -- Extraction rules (JSON with field→regex mappings)
    extraction_rules JSONB NOT NULL,

    -- Example:
    -- {
    --   "amount": {"regex": "\\$?([0-9]+\\.?[0-9]{0,2})", "type": "decimal"},
    --   "currency": {"regex": "([A-Z]{3})", "default": "USD"},
    --   "billing_cycle": {"regex": "(monthly|yearly)", "type": "enum"}
    -- }

    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0,  -- Higher priority checked first

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(provider_name, sender_pattern)
);

CREATE INDEX idx_templates_active ON email_templates(is_active, priority DESC);
```

---

## 4. API Specification

### 4.1 Authentication Endpoints

#### POST /api/auth/register
```json
Request:
{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response: 201 Created
{
  "id": "uuid",
  "email": "user@example.com",
  "access_token": "jwt_token",
  "refresh_token": "jwt_refresh_token",
  "token_type": "bearer"
}
```

#### POST /api/auth/login
```json
Request:
{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response: 200 OK
{
  "access_token": "jwt_token",
  "refresh_token": "jwt_refresh_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com"
  }
}
```

#### POST /api/auth/refresh
```json
Request:
{
  "refresh_token": "jwt_refresh_token"
}

Response: 200 OK
{
  "access_token": "new_jwt_token"
}
```

### 4.2 Mailbox Endpoints

#### POST /api/mailboxes
**Create/connect a new mailbox**
```json
Request:
{
  "provider_type": "jmap",
  "email_address": "user@fastmail.com",
  "credentials": {
    "jmap_url": "https://api.fastmail.com/jmap/",
    "access_token": "token",
    "refresh_token": "refresh_token"
  },
  "display_name": "My Fastmail",
  "sync_frequency": "weekly",
  "batch_size": 100,
  "import_date_filter": "2years"
}

Response: 201 Created
{
  "id": "uuid",
  "provider_type": "jmap",
  "email_address": "user@fastmail.com",
  "display_name": "My Fastmail",
  "is_active": true,
  "last_sync_at": null,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### GET /api/mailboxes
**List user's mailboxes**
```json
Response: 200 OK
{
  "mailboxes": [
    {
      "id": "uuid",
      "provider_type": "jmap",
      "email_address": "user@fastmail.com",
      "display_name": "My Fastmail",
      "is_active": true,
      "last_sync_at": "2024-01-15T10:30:00Z",
      "last_sync_status": "success"
    }
  ]
}
```

#### POST /api/mailboxes/{mailbox_id}/test-connection
**Test mailbox connection**
```json
Response: 200 OK
{
  "status": "success",
  "message": "Successfully connected to mailbox",
  "email_count": 15234
}
```

#### PUT /api/mailboxes/{mailbox_id}
**Update mailbox settings**

#### DELETE /api/mailboxes/{mailbox_id}
**Remove mailbox**

### 4.3 Email Processing Endpoints

#### POST /api/mailboxes/{mailbox_id}/import
**Trigger email import/sync**
```json
Request:
{
  "job_type": "import",  // or "sync"
  "date_filter": "2years",  // optional override
  "batch_size": 100  // optional override
}

Response: 202 Accepted
{
  "job_id": "uuid",
  "status": "queued",
  "message": "Import job queued successfully"
}
```

#### GET /api/jobs/{job_id}
**Get job status and progress**
```json
Response: 200 OK
{
  "id": "uuid",
  "job_type": "import",
  "status": "processing",
  "progress": {
    "total_emails": 1000,
    "processed_emails": 450,
    "accepted_count": 23,
    "rejected_count": 380,
    "pending_review_count": 47
  },
  "started_at": "2024-01-15T10:30:00Z",
  "estimated_completion": "2024-01-15T10:45:00Z"
}
```

#### GET /api/jobs/{job_id}/stream
**WebSocket endpoint for real-time progress updates**

### 4.4 Subscription Endpoints

#### GET /api/subscriptions
**List subscriptions with filtering**
```json
Query params:
- is_active: boolean
- category: string
- min_amount: decimal
- max_amount: decimal
- renewal_date_from: date
- renewal_date_to: date
- sort_by: string (amount, renewal_date, provider, created_at)
- sort_order: string (asc, desc)
- search: string
- page: int
- page_size: int

Response: 200 OK
{
  "subscriptions": [
    {
      "id": "uuid",
      "provider": "Netflix",
      "amount": 15.99,
      "currency": "EUR",
      "billing_cycle": "monthly",
      "renewal_date": "2024-02-01",
      "is_active": true,
      "category": "streaming",
      "tags": ["entertainment", "video"],
      "custom_label": null,
      "confidence_score": 95.5,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

#### GET /api/subscriptions/{subscription_id}
**Get subscription details**

#### POST /api/subscriptions
**Manually create subscription**
```json
Request:
{
  "provider": "Custom Service",
  "amount": 9.99,
  "currency": "EUR",
  "billing_cycle": "monthly",
  "renewal_date": "2024-02-01",
  "category": "software",
  "tags": ["productivity"],
  "custom_label": "Premium Plan",
  "notes": "Annual discount available"
}
```

#### PUT /api/subscriptions/{subscription_id}
**Update subscription**

#### DELETE /api/subscriptions/{subscription_id}
**Delete subscription**

#### GET /api/subscriptions/{subscription_id}/history
**Get subscription change history**

### 4.5 Email Review Endpoints

#### GET /api/email-reviews/pending
**Get emails pending manual review (50-84% confidence)**
```json
Response: 200 OK
{
  "pending_reviews": [
    {
      "id": "uuid",
      "email_subject": "Your Monthly Invoice",
      "email_sender": "billing@someservice.com",
      "email_date": "2024-01-10T08:00:00Z",
      "classification_confidence": 72.5,
      "extracted_data": {
        "provider": "SomeService",
        "amount": 19.99,
        "currency": "EUR",
        "billing_cycle": "monthly"
      },
      "validation_reason": "Medium confidence - unclear billing cycle pattern"
    }
  ],
  "count": 15
}
```

#### GET /api/email-reviews/rejected
**Get rejected emails (<50% confidence)**

#### POST /api/email-reviews/{record_id}/accept
**Manually accept an email and create subscription**
```json
Request:
{
  "subscription_data": {
    "provider": "SomeService",
    "amount": 19.99,
    "currency": "EUR",
    "billing_cycle": "monthly",
    "category": "software"
  },
  "update_ai_learning": true  // Add as training example
}
```

#### POST /api/email-reviews/{record_id}/reject
**Manually reject an email**

#### GET /api/email-reviews/{record_id}/email-content
**Fetch full email content for review**
```json
Response: 200 OK
{
  "subject": "Your Monthly Invoice",
  "sender": "billing@someservice.com",
  "date": "2024-01-10T08:00:00Z",
  "body_html": "<html>...",
  "body_text": "Plain text version..."
}
```

### 4.6 Analytics Endpoints

#### GET /api/analytics/spending-trends
**Get spending over time**
```json
Query params:
- period: monthly|yearly
- start_date: date
- end_date: date

Response: 200 OK
{
  "data": [
    {"period": "2024-01", "total": 145.50},
    {"period": "2024-02", "total": 152.30}
  ]
}
```

#### GET /api/analytics/category-breakdown
**Spending by category**
```json
Response: 200 OK
{
  "data": [
    {"category": "streaming", "total": 45.97, "count": 3},
    {"category": "software", "total": 89.97, "count": 5}
  ]
}
```

#### GET /api/analytics/top-expensive
**Most expensive subscriptions**
```json
Query params:
- limit: int (default 10)

Response: 200 OK
{
  "data": [
    {
      "provider": "Adobe Creative Cloud",
      "amount": 59.99,
      "billing_cycle": "monthly",
      "annual_cost": 719.88
    }
  ]
}
```

### 4.7 Budget Endpoints

#### GET /api/budgets
**Get user budgets**

#### POST /api/budgets
**Create budget**
```json
Request:
{
  "budget_type": "category",
  "category": "streaming",
  "amount": 50.00,
  "currency": "EUR",
  "period": "monthly",
  "alert_threshold": 90.0
}
```

#### PUT /api/budgets/{budget_id}
**Update budget**

#### GET /api/budgets/status
**Get current budget status**
```json
Response: 200 OK
{
  "overall": {
    "budget": 200.00,
    "current": 145.50,
    "percentage": 72.75,
    "status": "ok"
  },
  "by_category": [
    {
      "category": "streaming",
      "budget": 50.00,
      "current": 45.97,
      "percentage": 91.94,
      "status": "warning"
    }
  ]
}
```

### 4.8 Settings Endpoints

#### GET /api/settings
**Get user settings**

#### PUT /api/settings
**Update settings**
```json
Request:
{
  "confidence_thresholds": {
    "auto_accept": 85.0,
    "manual_review_min": 50.0
  },
  "ai_model": "gpt-4o-mini",
  "default_currency": "EUR",
  "notifications_enabled": true
}
```

### 4.9 Data Export Endpoints

#### GET /api/export/subscriptions
**Export all subscription data**
```json
Query params:
- format: json|csv

Response: 200 OK (file download)
```

#### DELETE /api/user/data
**Delete all user data (GDPR compliance)**

---

## 5. AI/LLM Strategy

### 5.1 OpenAI Assistant Configuration

**Assistant Creation**
```python
assistant = client.beta.assistants.create(
    name="Subscription Email Analyzer",
    instructions="""You are an expert at analyzing emails to identify subscription-related communications.

Your task is two-fold:
1. CLASSIFICATION: Determine if an email is about a subscription (recurring payment)
2. EXTRACTION: If yes, extract structured subscription data

CLASSIFICATION CRITERIA:
- Look for recurring payment language (monthly, yearly, subscription, renewal)
- Identify billing/payment notifications
- Detect service provider names
- Be cautious with one-time purchases or receipts
- Support both French and English emails

EXTRACTION REQUIREMENTS:
Extract these fields:
- provider: Company/service name
- amount: Numeric value only
- currency: 3-letter code (EUR, USD, etc.)
- billing_cycle: monthly, yearly, quarterly, or other
- renewal_date: YYYY-MM-DD format if available
- subscription_id: Any subscription/account ID if present

EDGE CASES:
- PayPal/payment processor emails: Extract the actual service provider, not PayPal
- Multiple subscriptions in one email: Extract the primary one
- Gifts/trials: Mark as subscription only if recurring payment confirmed
- Cancellation emails: Mark as subscription but note if cancelled

Return confidence score (0-100) for your classification.""",
    model="gpt-4o-mini",
    tools=[
        {
            "type": "function",
            "function": {
                "name": "extract_subscription_data",
                "description": "Extract structured subscription information from email",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_subscription": {
                            "type": "boolean",
                            "description": "Is this a subscription-related email?"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-100"
                        },
                        "provider": {"type": "string"},
                        "amount": {"type": "number"},
                        "currency": {"type": "string"},
                        "billing_cycle": {
                            "type": "string",
                            "enum": ["monthly", "yearly", "quarterly", "other"]
                        },
                        "renewal_date": {"type": "string"},
                        "subscription_id": {"type": "string"},
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of classification decision"
                        }
                    },
                    "required": ["is_subscription", "confidence", "reasoning"]
                }
            }
        }
    ]
)
```

### 5.2 Template-Based Extraction (Phase 1)

**Hardcoded Templates for Common Providers**
```python
TEMPLATES = {
    "netflix": {
        "sender_pattern": r".*@netflix\.com",
        "subject_pattern": r".*payment|receipt|invoice.*",
        "extraction": {
            "amount": r"(?:€|EUR|USD|\$)\s*([0-9]+\.?[0-9]{0,2})",
            "billing_cycle": "monthly",  # default
            "provider": "Netflix"
        }
    },
    "spotify": {
        "sender_pattern": r".*@spotify\.com",
        "subject_pattern": r".*receipt|payment.*",
        "extraction": {
            "amount": r"([0-9]+\.?[0-9]{0,2})\s*(?:€|EUR|USD|\$)",
            "billing_cycle": "monthly",
            "provider": "Spotify"
        }
    },
    # Add more common providers...
}
```

### 5.3 Two-Stage Processing

**Stage 1: Classification**
```python
def classify_email(email_content: str) -> tuple[bool, float]:
    """
    Returns: (is_subscription, confidence_score)
    """
    # Try template matching first
    for template in TEMPLATES.values():
        if matches_template(email_content, template):
            return True, 100.0  # Perfect confidence for known patterns

    # Fall back to AI classification
    response = openai_assistant.classify(email_content)
    return response.is_subscription, response.confidence
```

**Stage 2: Extraction**
```python
def extract_subscription_data(email_content: str, classification_confidence: float):
    """
    Extract structured data from email
    """
    # Try template extraction
    template_match = find_matching_template(email_content)
    if template_match:
        return extract_with_template(email_content, template_match)

    # Use AI extraction
    return openai_assistant.extract(email_content)
```

### 5.4 Learning from User Feedback

**When user manually accepts a rejected email:**
```python
def learn_from_acceptance(email_record, user_corrections):
    """
    Store as few-shot example for future prompts
    """
    training_example = {
        "email_subject": email_record.email_subject,
        "email_body_snippet": email_record.get_body_snippet(),
        "correct_extraction": user_corrections,
        "original_confidence": email_record.classification_confidence,
        "accepted_at": datetime.now()
    }

    # Store in database for later use in prompts
    store_training_example(training_example)

    # Optionally: suggest creating a template if pattern detected
    if should_suggest_template(training_example):
        notify_admin_for_template_creation(training_example)
```

### 5.5 Deduplication Intelligence

**Multi-Factor Deduplication Logic**
```python
def find_duplicates(new_subscription, existing_subscriptions):
    """
    Intelligent duplicate detection
    """
    duplicates = []

    for existing in existing_subscriptions:
        score = 0

        # Factor 1: Email sender similarity
        if similar_sender(new_subscription.email_sender, existing.email_sender):
            score += 30

        # Factor 2: Provider name match
        if fuzzy_match(new_subscription.provider, existing.provider, threshold=0.85):
            score += 40

        # Factor 3: Amount similarity (within 5%)
        if amounts_similar(new_subscription.amount, existing.amount, tolerance=0.05):
            score += 20

        # Factor 4: Billing cycle match
        if new_subscription.billing_cycle == existing.billing_cycle:
            score += 10

        # Factor 5: Time proximity (same month)
        if same_billing_period(new_subscription.renewal_date, existing.renewal_date):
            score += 10

        # Special case: Payment processor detection
        if is_payment_processor(new_subscription.email_sender):
            # Check if existing subscription matches the actual provider
            if new_subscription.provider in existing.provider:
                score += 50  # High confidence it's a duplicate via PayPal

        if score >= 70:  # Threshold for duplicate
            duplicates.append((existing, score))

    return duplicates
```

**Auto-Merge Logic**
```python
def auto_merge_duplicates(new_sub, duplicate_sub, merge_score):
    """
    Merge duplicate subscriptions, preferring non-payment-processor
    """
    if is_payment_processor(new_sub.email_sender):
        # Keep existing, store PayPal as metadata
        duplicate_sub.payment_processor = {
            "provider": "paypal",
            "email": new_sub.email_sender
        }
        duplicate_sub.save()
        return duplicate_sub
    else:
        # Update existing with new info if more reliable
        if new_sub.confidence_score > duplicate_sub.confidence_score:
            duplicate_sub.update_from(new_sub)
        duplicate_sub.last_confirmed_at = datetime.now()
        duplicate_sub.save()
        return duplicate_sub
```

---

## 6. Frontend Architecture

### 6.1 Project Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── auth/
│   │   │   ├── LoginForm.tsx
│   │   │   ├── RegisterForm.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── subscriptions/
│   │   │   ├── SubscriptionList.tsx
│   │   │   ├── SubscriptionCard.tsx
│   │   │   ├── SubscriptionFilters.tsx
│   │   │   ├── SubscriptionForm.tsx
│   │   │   └── SubscriptionDetails.tsx
│   │   ├── mailboxes/
│   │   │   ├── MailboxList.tsx
│   │   │   ├── MailboxForm.tsx
│   │   │   ├── MailboxConnection.tsx
│   │   │   └── ImportProgress.tsx
│   │   ├── reviews/
│   │   │   ├── PendingReviewList.tsx
│   │   │   ├── EmailReviewCard.tsx
│   │   │   └── EmailViewer.tsx
│   │   ├── analytics/
│   │   │   ├── SpendingTrends.tsx
│   │   │   ├── CategoryBreakdown.tsx
│   │   │   ├── TopExpensive.tsx
│   │   │   └── BudgetStatus.tsx
│   │   ├── common/
│   │   │   ├── Layout.tsx
│   │   │   ├── Navigation.tsx
│   │   │   ├── ProgressBar.tsx
│   │   │   └── ConfidenceBadge.tsx
│   │   └── settings/
│   │       ├── UserSettings.tsx
│   │       ├── AISettings.tsx
│   │       └── BudgetSettings.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useSubscriptions.ts
│   │   ├── useMailboxes.ts
│   │   ├── useEmailReviews.ts
│   │   ├── useAnalytics.ts
│   │   └── useWebSocket.ts
│   ├── contexts/
│   │   ├── AuthContext.tsx
│   │   └── SettingsContext.tsx
│   ├── api/
│   │   ├── client.ts
│   │   ├── auth.ts
│   │   ├── subscriptions.ts
│   │   ├── mailboxes.ts
│   │   ├── reviews.ts
│   │   └── analytics.ts
│   ├── types/
│   │   ├── subscription.ts
│   │   ├── mailbox.ts
│   │   ├── user.ts
│   │   └── api.ts
│   ├── utils/
│   │   ├── formatting.ts
│   │   ├── validation.ts
│   │   └── constants.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 6.2 Key React Query Hooks

**useSubscriptions.ts**
```typescript
export function useSubscriptions(filters?: SubscriptionFilters) {
  return useQuery({
    queryKey: ['subscriptions', filters],
    queryFn: () => subscriptionsApi.list(filters),
    staleTime: 30000, // 30 seconds
  });
}

export function useCreateSubscription() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: subscriptionsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });
}
```

**useImportProgress.ts**
```typescript
export function useImportProgress(jobId: string) {
  const [progress, setProgress] = useState<JobProgress | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/api/jobs/${jobId}/stream`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress(data);
    };

    return () => ws.close();
  }, [jobId]);

  return progress;
}
```

### 6.3 Dashboard Layout

**Main Dashboard Components**
1. **Header**: Navigation, user menu, settings
2. **Sidebar**: Quick stats, budget status, filters
3. **Main Content**:
   - Subscription list with sort/filter
   - Charts section (spending trends, category breakdown)
   - Pending reviews count/link
4. **Modals**: Add subscription, edit subscription, view email

---

## 7. Email Provider Interface

### 7.1 Unified Provider Interface

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

### 7.2 JMAP Implementation (Phase 1)

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

### 7.3 Provider Factory

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

---

## 8. Celery Task Architecture

### 8.1 Task Structure

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

### 8.2 Email Processor Service

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

---

## 9. Docker Setup

### 9.1 docker-compose.dev.yml

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: subscriptions_db
    environment:
      POSTGRES_DB: subscription_tracker
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: devpassword
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Redis (for Celery broker and cache)
  redis:
    image: redis:7-alpine
    container_name: subscriptions_redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: subscriptions_backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DATABASE_URL: postgresql://postgres:devpassword@postgres:5432/subscription_tracker
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      CORS_ORIGINS: http://localhost:5173
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - /app/__pycache__  # Exclude cache
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # Celery Worker
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: subscriptions_celery
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://postgres:devpassword@postgres:5432/subscription_tracker
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    volumes:
      - ./backend:/app
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  # Celery Beat (for periodic tasks)
  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: subscriptions_celery_beat
    command: celery -A app.celery_app beat --loglevel=info
    environment:
      DATABASE_URL: postgresql://postgres:devpassword@postgres:5432/subscription_tracker
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./backend:/app
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: subscriptions_frontend
    command: npm run dev -- --host
    environment:
      VITE_API_URL: http://localhost:8000
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules  # Exclude node_modules
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
```

### 9.2 Backend Dockerfile.dev

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Development mode (code hot-reload via volume mount)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### 9.3 Frontend Dockerfile.dev

```dockerfile
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Development mode (Vite hot-reload)
CMD ["npm", "run", "dev", "--", "--host"]
```

### 9.4 Environment Variables (.env.example)

```bash
# Database
DATABASE_URL=postgresql://postgres:devpassword@localhost:5432/subscription_tracker

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Security
JWT_SECRET_KEY=your-very-secure-secret-key-change-this
ENCRYPTION_KEY=your-encryption-key-32-characters

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Email Provider (for testing)
JMAP_URL=https://api.fastmail.com/jmap/
```

---

## 10. Security Implementation

### 10.1 Password Hashing

```python
# backend/app/security/password.py
import bcrypt

def hash_password(password: str) -> tuple[str, str]:
    """Hash password with bcrypt and return (hash, salt)"""
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    return password_hash.decode('utf-8'), salt.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(
        password.encode('utf-8'),
        password_hash.encode('utf-8')
    )
```

### 10.2 JWT Authentication

```python
# backend/app/security/jwt.py
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "user_id": user_id,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 10.3 Credential Encryption

```python
# backend/app/security/encryption.py
from cryptography.fernet import Fernet
import os
import json

# Load encryption key from environment
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
cipher = Fernet(ENCRYPTION_KEY)

def encrypt_credentials(credentials: dict) -> str:
    """Encrypt credentials dictionary to string"""
    json_str = json.dumps(credentials)
    encrypted = cipher.encrypt(json_str.encode())
    return encrypted.decode()

def decrypt_credentials(encrypted_credentials: str) -> dict:
    """Decrypt credentials string to dictionary"""
    decrypted = cipher.decrypt(encrypted_credentials.encode())
    return json.loads(decrypted.decode())

# Generate encryption key (run once, store in environment)
def generate_encryption_key() -> str:
    return Fernet.generate_key().decode()
```

### 10.4 CORS Configuration

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

---

## 11. Development Workflow

### 11.1 Initial Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd subscription_tracker

# 2. Create .env file
cp .env.example .env
# Edit .env with your keys

# 3. Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env as ENCRYPTION_KEY

# 4. Start all services
docker-compose -f docker-compose.dev.yml up -d

# 5. Run database migrations
docker-compose exec backend alembic upgrade head

# 6. Create first user (optional)
docker-compose exec backend python scripts/create_user.py

# 7. Access application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 11.2 Common Development Commands

```bash
# View logs
docker-compose -f docker-compose.dev.yml logs -f backend
docker-compose -f docker-compose.dev.yml logs -f celery_worker

# Restart a service
docker-compose -f docker-compose.dev.yml restart backend

# Run database migrations
docker-compose exec backend alembic revision --autogenerate -m "description"
docker-compose exec backend alembic upgrade head

# Access database
docker-compose exec postgres psql -U postgres -d subscription_tracker

# Access Redis CLI
docker-compose exec redis redis-cli

# Run tests
docker-compose exec backend pytest

# Install new Python package
docker-compose exec backend pip install <package>
# Then update requirements.txt

# Install new npm package
docker-compose exec frontend npm install <package>
```

### 11.3 Database Migrations

```bash
# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "add custom_label to subscriptions"

# Review migration file in backend/alembic/versions/

# Apply migration
docker-compose exec backend alembic upgrade head

# Rollback migration
docker-compose exec backend alembic downgrade -1
```

---

## 12. Phase Roadmap

### Phase 1: MVP (Months 1-2)

**Core Features:**
- ✅ User authentication (email/password + JWT)
- ✅ JMAP email integration
- ✅ Email import with progress tracking
- ✅ AI-powered classification & extraction (GPT-4o-mini)
- ✅ Template matching for 5-10 common providers
- ✅ Subscription CRUD operations
- ✅ Basic dashboard with list view
- ✅ Confidence-based routing (auto-accept/review/reject)
- ✅ Manual review interface for pending emails
- ✅ Basic deduplication logic
- ✅ Data export (JSON/CSV)
- ✅ User data deletion

**Analytics (Basic):**
- ✅ Monthly spending trends chart
- ✅ Category breakdown pie chart
- ✅ Top 10 expensive subscriptions

**Infrastructure:**
- ✅ Docker Compose dev environment
- ✅ PostgreSQL database
- ✅ FastAPI backend with hot-reload
- ✅ React + TypeScript frontend with Vite
- ✅ Celery + Redis for background jobs
- ✅ Basic error handling and logging

### Phase 2: Enhanced Features (Months 3-4)

**Email Integration:**
- ✅ Gmail OAuth integration
- ✅ Outlook OAuth integration
- ✅ Multiple mailbox support per user
- ✅ Configurable sync frequency
- ✅ Re-process emails feature

**AI & Templates:**
- ✅ Template builder UI (admin/power users)
- ✅ Learning from user feedback (store examples)
- ✅ Template testing interface
- ✅ Expand template library to 20+ providers

**Analytics:**
- ✅ Budget tracking (overall + per category)
- ✅ Budget alerts
- ✅ Spending forecasting
- ✅ Subscription lifecycle analysis
- ✅ Renewal calendar view

**UX Improvements:**
- ✅ Advanced filtering and search
- ✅ Bulk operations (tag multiple, delete multiple)
- ✅ Subscription notes and attachments
- ✅ Custom categories management
- ✅ Dark mode

### Phase 3: AI Excellence (Months 5-6)

**AI Enhancements:**
- ✅ AI-assisted template generation from examples
- ✅ Fine-tuning on user feedback data
- ✅ Multi-provider duplicate detection improvements
- ✅ Anomaly detection (price changes, unusual charges)
- ✅ Smart categorization suggestions

**Advanced Features:**
- ✅ Subscription sharing (family accounts)
- ✅ Renewal reminders (email notifications)
- ✅ Cancellation tracking
- ✅ Cost optimization suggestions
- ✅ Similar subscription recommendations

**API & Integrations:**
- ✅ Public API for third-party integrations
- ✅ Browser extension for quick subscription adding
- ✅ Mobile app (React Native)
- ✅ Zapier/Make integration

### Phase 4: Scale & Polish (Months 7-8)

**Performance:**
- ✅ Database query optimization
- ✅ Caching strategy (Redis)
- ✅ Batch processing improvements
- ✅ CDN for static assets

**Security & Compliance:**
- ✅ Full GDPR compliance
- ✅ SOC 2 compliance preparation
- ✅ Advanced audit logging
- ✅ Two-factor authentication

**Deployment:**
- ✅ Production Docker Compose setup
- ✅ CI/CD pipeline (GitHub Actions)
- ✅ Database backup strategy
- ✅ Monitoring and alerting (Sentry, Datadog)
- ✅ Load balancing and horizontal scaling

**Monetization:**
- ✅ Free tier limits (3 mailboxes, 100 subscriptions)
- ✅ Premium subscription tiers
- ✅ Stripe payment integration

---

## 13. Testing Strategy

### 13.1 Backend Tests

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

@pytest.mark.asyncio
async def test_deduplication():
    deduplicator = Deduplicator(user_id="test")
    # Create existing subscription
    existing = create_subscription(provider="Netflix", amount=15.99)

    # New email from PayPal for Netflix
    new_data = {
        "provider": "Netflix",
        "amount": 15.99,
        "email_sender": "service@paypal.com"
    }

    duplicates = deduplicator.find_duplicates(new_data)
    assert len(duplicates) == 1
    assert duplicates[0].id == existing.id
```

### 13.2 Frontend Tests

```typescript
// frontend/src/components/subscriptions/__tests__/SubscriptionList.test.tsx
import { render, screen } from '@testing-library/react';
import { SubscriptionList } from '../SubscriptionList';

test('renders subscription list', () => {
  const subscriptions = [
    { id: '1', provider: 'Netflix', amount: 15.99 },
    { id: '2', provider: 'Spotify', amount: 9.99 },
  ];

  render(<SubscriptionList subscriptions={subscriptions} />);

  expect(screen.getByText('Netflix')).toBeInTheDocument();
  expect(screen.getByText('$15.99')).toBeInTheDocument();
});
```

---

## 14. Monitoring & Logging

### 14.1 Application Logging

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

### 14.2 Error Tracking (Future: Sentry)

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

---

## 15. Next Steps

### Immediate (Week 1)
1. Set up project structure (backend + frontend directories)
2. Configure Docker Compose for development
3. Create database schema and initial migration
4. Implement user authentication endpoints
5. Set up FastAPI project with basic routes

### Week 2
1. Implement JMAP provider interface
2. Create email import Celery task
3. Build basic AI classification with OpenAI
4. Develop subscription CRUD endpoints

### Week 3
1. Implement React frontend structure
2. Create authentication flow (login/register)
3. Build subscription list component
4. Add progress tracking for email import

### Week 4
1. Implement manual review interface
2. Add deduplication logic
3. Create template matching for 5 providers
4. Build basic analytics charts

---

## Appendix A: Technology Choices Rationale

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

---

## Appendix B: Open Questions

1. **Email retention**: How long to keep email processing records?
2. **AI costs**: Budget for OpenAI API usage at scale?
3. **Backup strategy**: Frequency and retention for database backups?
4. **Production hosting**: Cloud provider preference (AWS, GCP, Azure, DigitalOcean)?
5. **Domain name**: What domain for production deployment?

---

**Document Version**: 1.0
**Last Updated**: 2024-01-15
**Authors**: Claude Code + User Requirements Discovery
