# Data Model

> Source of truth for the subscription_tracker database schema. Migration files live in `backend/alembic/versions/`.

PostgreSQL 15+ with JSONB, full-text search, and triggers. UUID primary keys for all tables. `created_at` / `updated_at` timestamps on most tables. Soft deletes via `is_active` boolean where applicable. JSONB for flexible/structured metadata fields.

## 3.1 Users Table

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

## 3.2 Mailboxes Table

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

## 3.3 Subscriptions Table

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

Notes:
- `custom_label` differentiates same-provider subscriptions (e.g., Twitch streamer name). MVP keeps a single column; could migrate to JSONB in Phase 2 if richer disambiguation is needed.
- `payment_processor` JSONB captures PayPal → actual provider mapping (see deduplication.md).
- `confidence_score` (0–100) drives routing; see ai-strategy.md.

## 3.4 Subscription History Table

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

## 3.5 Email Processing Records Table

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

`email_id` is provider-specific and used for re-fetching. `extracted_data` is JSONB and may need explicit casting in raw SQL.

## 3.6 Budgets Table

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

## 3.7 Processing Jobs Table

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

## 3.8 Templates Table (Phase 1: Hardcoded, Phase 2+: User-created)

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

## Conventions

- **Multi-tenancy**: every query filters by `user_id`. There is no PostgreSQL RLS in Phase 1; see security.md.
- **JSONB fields**: `users.settings`, `subscriptions.payment_processor`, `email_processing_records.extracted_data`, `processing_jobs.config`, `email_templates.extraction_rules`. Cast explicitly in raw SQL.
- **Encrypted columns**: `mailboxes.encrypted_credentials` is Fernet-encrypted JSON; decrypt before use.
