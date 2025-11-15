# Session: AI Classifier Improvement - November 15, 2025

## Session Summary
Improved AI email classifier to reduce false positives in subscription detection. The classifier was too aggressive, marking login notifications, AWS alerts, and marketing emails as subscriptions.

## Key Changes Made

### 1. AI Classifier Prompt Overhaul
**File**: `backend/app/services/ai_classifier.py`

**Problem**: Classifier was too broad, causing false positives:
- AWS Lambda technical alerts (0.95 confidence)
- Amazon login notifications (0.95 confidence)
- Crunchyroll login alerts (0.95 confidence)
- PayPal one-time receipts (0.90 confidence)
- Marketing emails (0.80-0.90 confidence)

**Solution**: Complete prompt rewrite with:
1. **Focus shift**: From "account notifications" to "billing/payment/renewal emails only"
2. **Explicit exclusions**: Added HIGH PRIORITY sections for:
   - Security & Account Access (login notifications, password resets)
   - Service Notifications (AWS alerts, usage warnings)
   - Marketing & Engagement (newsletters, content notifications)
3. **Real-world examples**: Used actual problem emails as negative examples
4. **Confidence rules**: Force low confidence (< 0.3) for security/technical alerts

### 2. Critical Bug Fix (From Previous Session)
**File**: `backend/app/tasks/email_sync.py` (lines 178-195)

**Problem**: Transaction rollback caused by JSON serialization error
- Python `datetime` objects can't be stored in PostgreSQL JSONB columns
- This caused subscriptions to be created but then rolled back
- Counter showed "1 subs" but database had 0

**Solution**: Convert datetime objects to ISO strings before JSONB storage:
```python
extraction_data_json = {}
for key, value in subscription_data.items():
    if isinstance(value, datetime):
        extraction_data_json[key] = value.isoformat()
    else:
        extraction_data_json[key] = value
```

### 3. Confidence Score Display Fix (From Previous Session)
**File**: `frontend/src/components/subscriptions/SubscriptionDetailPage.tsx` (line 204)

**Problem**: Showing "1%" instead of "100%" for confidence 1.0

**Solution**: Multiply by 100 in display:
```typescript
`${(subscription.confidence_score * 100).toFixed(0)}%`
```

## Classifier Improvements Details

### Before (Too Aggressive):
```
SUBSCRIPTION SERVICE types to look for:
- Streaming services (Netflix, Disney+, Crunchyroll, Twitch, Prime Video, etc.)
- SaaS/Cloud services (AWS, Google Cloud, Dropbox, Adobe, Microsoft 365, etc.)
- Gaming services (PlayStation Plus, Xbox Live, Riot Games, Steam, etc.)
- Newsletter subscriptions (TLDR, Medium, Substack, blogs, etc.)

Subscription indicators in emails:
- Account notifications from subscription services
- Usage alerts/warnings (e.g., "AWS Lambda end of support")
- New content notifications from subscribed services/newsletters
```

### After (Conservative & Precise):
```
✅ SUBSCRIPTION-RELATED EMAILS (is_subscription: true):

1. **Billing & Payment Emails**:
   - Payment confirmations for subscription services
   - Billing statements/invoices for recurring services
   - Payment method updates for subscriptions
   - Failed payment notifications for subscriptions

2. **Renewal & Trial Emails**:
   - Renewal reminders
   - Trial ending notices
   - Auto-renewal confirmations
   - Subscription expiration notices

🚫 NOT SUBSCRIPTION-RELATED (is_subscription: false):

1. **Security & Account Access** (HIGH PRIORITY):
   - Login notifications
   - Password resets
   - Security alerts
   - Two-factor authentication codes

2. **Service Notifications** (HIGH PRIORITY):
   - Technical alerts (e.g., "AWS Lambda end of support")
   - Usage warnings
   - Service status/downtime notifications

⚠️ CRITICAL DISTINCTIONS:

**Amazon Emails**:
- ❌ "Someone signed in to your Amazon account" → NOT subscription (login alert)
- ✅ "Your Amazon Prime membership renews on..." → IS subscription (renewal)

**AWS/Cloud Emails**:
- ❌ "AWS Lambda end of support notification" → NOT subscription (service alert)
- ✅ "Your AWS invoice is ready" → IS subscription (billing)

**Streaming Services**:
- ❌ "New login from Windows PC" → NOT subscription (security alert)
- ✅ "Your Crunchyroll subscription renews on 12/15" → IS subscription (renewal)

CLASSIFICATION RULES:
1. If email is about LOGIN, SECURITY, or TECHNICAL ALERTS → confidence must be LOW (< 0.3)
2. If email mentions BILLING, PAYMENT, RENEWAL, TRIAL → check if it's for a subscription service
3. Only use confidence > 0.8 for clear billing/payment/renewal emails
```

## Testing Status
- ✅ Code changes completed
- ✅ Celery worker restarted with new classifier
- ⏳ Awaiting user testing from frontend

## Next Steps (User Requested)
1. ✅ **Improve AI Classifier Accuracy** - COMPLETED
2. 🔜 **AI Sandbox Feature** (Future priority):
   - Allow pasting email content into frontend
   - Test classification/extraction in real-time
   - Show AI reasoning
   - Iteratively improve prompts
   - Create templates from successful patterns

## Technical Context

### Architecture
- **Backend**: FastAPI + Celery + PostgreSQL
- **Frontend**: React + TypeScript + Chakra UI
- **AI**: OpenAI GPT-4o-mini for classification/extraction
- **Email**: JMAP protocol with Fastmail

### Key Files
1. `backend/app/services/ai_classifier.py` - Email classification logic
2. `backend/app/tasks/email_sync.py` - Sync workflow with transaction handling
3. `frontend/src/components/subscriptions/SubscriptionDetailPage.tsx` - UI display

### Database Schema Notes
- `subscription_emails` junction table has JSONB `extraction_data` column
- Foreign keys have CASCADE DELETE (caused data loss issue in previous session)
- `subscriptions.currency` column is nullable

## Lessons Learned
1. **JSON Serialization**: Always convert Python datetime to ISO strings before JSONB storage
2. **Prompt Engineering**: Explicit negative examples dramatically improve AI accuracy
3. **Confidence Calibration**: Force low confidence for ambiguous cases, high only for clear matches
4. **Real-World Testing**: Use actual problem emails as examples in prompts

## Database Details
- **Mailbox ID**: 3f4605c1-5544-4fb9-b0c7-de08e4325543
- **User Email**: dev@ankirama.com
- **Sync Window**: 90 days (extended from 30 days)

## Previous Session Issues (Resolved)
1. ❌ Duplicate mailbox issue → Fixed by merging subscriptions
2. ❌ CASCADE DELETE data loss → Fixed by cleaning orphaned data
3. ❌ JSON serialization error → Fixed with datetime conversion
4. ❌ Confidence display bug → Fixed with percentage calculation
