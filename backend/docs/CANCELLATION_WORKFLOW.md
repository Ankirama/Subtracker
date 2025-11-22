# Cancellation Workflow Documentation

Visual guide and technical flow documentation for the subscription cancellation feature.

## Table of Contents
1. [User Journey Overview](#user-journey-overview)
2. [Technical Architecture](#technical-architecture)
3. [Workflow States](#workflow-states)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Integration Points](#integration-points)
6. [Error Handling](#error-handling)

---

## User Journey Overview

### Complete User Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISCOVERY PHASE                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    User logs into app
                              │
                              ▼
                  Navigates to Review Dashboard
                    (/reviews endpoint)
                              │
                              ▼
         ┌──────────────────────────────────────────┐
         │  GET /api/reviews/suggestions            │
         │                                          │
         │  Returns:                                │
         │  - AI-generated review suggestions       │
         │  - Priority classifications              │
         │  - Reason codes                          │
         │  - Activity analysis                     │
         └──────────────────────────────────────────┘
                              │
                              ▼
              User sees personalized dashboard
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  Statistics Cards Display:                  │
        │  - Total suggestions count                  │
        │  - Critical priority count                  │
        │  - High priority count                      │
        │  - Potential monthly savings                │
        └─────────────────────────────────────────────┘
                              │
                              ▼
              User applies filters (optional)
        (Priority filter, Reason filter)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INVESTIGATION PHASE                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
           User clicks suggestion card
                              │
                              ▼
      Navigate to Subscription Detail Page
           (/subscriptions/:id)
                              │
                              ▼
         User clicks "Cancellation" tab
                              │
                              ▼
         ┌──────────────────────────────────────────┐
         │  GET /api/subscriptions/{id}/cancellation│
         │                                          │
         │  Returns:                                │
         │  - Current cancellation status           │
         │  - Provider info (if researched)         │
         │  - User notes                            │
         └──────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESEARCH PHASE                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
    User clicks "Research Cancellation Instructions"
                              │
                              ▼
         ┌──────────────────────────────────────────┐
         │  POST /api/cancellation/research         │
         │                                          │
         │  Request:                                │
         │  {                                       │
         │    "provider_name": "Netflix",           │
         │    "force_refresh": false                │
         │  }                                       │
         └──────────────────────────────────────────┘
                              │
                              ▼
                  Check provider cache
                              │
                 ┌────────────┴─────────────┐
                 │                          │
            Cache Hit?                  Cache Miss?
                 │                          │
                 ▼                          ▼
       Return cached data          Call OpenAI GPT-4
                 │                          │
                 │                          ▼
                 │                 Analyze provider:
                 │                 - Cancellation URL
                 │                 - Difficulty rating
                 │                 - Step-by-step instructions
                 │                 - Requirements (phone/chat)
                 │                 - Pause options
                 │                 - Gotchas & warnings
                 │                          │
                 │                          ▼
                 │                 Store in database
                 │                 (30-day cache)
                 │                          │
                 └────────────┬─────────────┘
                              │
                              ▼
         ┌──────────────────────────────────────────┐
         │  Response:                               │
         │  {                                       │
         │    "provider_name": "Netflix",           │
         │    "cancellation_url": "...",            │
         │    "difficulty_rating": "easy",          │
         │    "instructions": [...],                │
         │    "requires_phone_call": false,         │
         │    "allows_pause": true,                 │
         │    "estimated_time_minutes": 5,          │
         │    "cancellation_gotchas": [...],        │
         │    "ai_confidence_score": 0.95           │
         │  }                                       │
         └──────────────────────────────────────────┘
                              │
                              ▼
          Frontend displays instructions
                              │
                              ▼
            User reviews instructions
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION PHASE                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
     User updates status to "ready_to_cancel"
                              │
                              ▼
         ┌──────────────────────────────────────────┐
         │  PATCH /api/subscriptions/{id}/          │
         │        cancellation/status               │
         │                                          │
         │  Request:                                │
         │  {                                       │
         │    "status": "ready_to_cancel",          │
         │    "notes": "Planning to cancel today"   │
         │  }                                       │
         └──────────────────────────────────────────┘
                              │
                              ▼
           Status updated in database
                              │
                              ▼
      User opens provider website (new tab)
                              │
                              ▼
           Follows instructions step-by-step
                              │
                              ▼
     User updates status to "cancellation_initiated"
                              │
                              ▼
         ┌──────────────────────────────────────────┐
         │  PATCH /api/subscriptions/{id}/          │
         │        cancellation/status               │
         │                                          │
         │  - Sets cancellation_initiated_at        │
         │    timestamp (immutable)                 │
         │  - Updates status                        │
         └──────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETION PHASE                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
     User receives confirmation from provider
                              │
                              ▼
        User updates status to "completed"
                              │
                              ▼
         ┌──────────────────────────────────────────┐
         │  PATCH /api/subscriptions/{id}/          │
         │        cancellation/status               │
         │                                          │
         │  - Sets cancellation_completed_at        │
         │    timestamp (immutable)                 │
         │  - Marks as completed (final state)      │
         └──────────────────────────────────────────┘
                              │
                              ▼
            Cancellation complete! ✅
                              │
                              ▼
         User returns to Review Dashboard
        (Suggestion removed from active list)
```

---

## Technical Architecture

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ReviewDashboardPage.tsx                                         │
│  ├─ Statistics Cards                                             │
│  ├─ Filter Controls                                              │
│  └─ Suggestion List                                              │
│     └─ SuggestionCard (clickable)                                │
│                                                                  │
│  SubscriptionDetailPage.tsx                                      │
│  └─ Tabs                                                         │
│     └─ CancellationTab                                           │
│        └─ CancellationInstructions.tsx                           │
│           ├─ Research Button                                     │
│           ├─ Instructions Display                                │
│           └─ Status Manager                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│                         BACKEND API                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FastAPI Routers:                                                │
│  ├─ /api/reviews/suggestions                                     │
│  │  └─ review_suggestions.py                                     │
│  │     └─ ReviewSuggestionsService                               │
│  │                                                               │
│  ├─ /api/cancellation/research                                   │
│  │  └─ cancellation.py                                           │
│  │     └─ CancellationService                                    │
│  │        └─ OpenAI GPT-4 Integration                            │
│  │                                                               │
│  └─ /api/subscriptions/{id}/cancellation                         │
│     └─ subscriptions.py                                          │
│        └─ SubscriptionService                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SQLAlchemy ORM
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│                         DATABASE                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Tables:                                                         │
│  ├─ subscriptions                                                │
│  │  └─ Core subscription data                                    │
│  │                                                               │
│  ├─ provider_cancellation_info                                   │
│  │  ├─ provider_name (unique)                                    │
│  │  ├─ cancellation_url                                          │
│  │  ├─ difficulty_rating                                         │
│  │  ├─ instructions (JSONB)                                      │
│  │  ├─ requires_phone_call                                       │
│  │  ├─ requires_chat                                             │
│  │  ├─ allows_pause                                              │
│  │  ├─ pause_instructions (JSONB)                                │
│  │  ├─ estimated_time_minutes                                    │
│  │  ├─ cancellation_gotchas (JSONB)                              │
│  │  ├─ ai_confidence_score                                       │
│  │  ├─ is_ai_generated                                           │
│  │  ├─ created_at (for 30-day cache)                             │
│  │  └─ updated_at                                                │
│  │                                                               │
│  └─ subscription_cancellation_info                               │
│     ├─ subscription_id (foreign key)                             │
│     ├─ status (enum)                                             │
│     ├─ cancellation_initiated_at (immutable)                     │
│     ├─ cancellation_completed_at (immutable)                     │
│     ├─ notes (text)                                              │
│     ├─ created_at                                                │
│     └─ updated_at                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ External API
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│                      OPENAI GPT-4                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AI Cancellation Research:                                       │
│  - Analyzes provider cancellation procedures                     │
│  - Generates step-by-step instructions                           │
│  - Estimates difficulty and time                                 │
│  - Identifies gotchas and alternatives                           │
│  - Confidence scoring                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Workflow States

### State Machine Diagram

```
                              START
                                │
                                ▼
                        ┌──────────────┐
                        │ considering  │ ◄─────────────┐
                        └──────────────┘               │
                                │                      │
                                ▼                      │
                        ┌──────────────┐               │
                        │ researching  │               │
                        └──────────────┘               │
                                │                      │
                                ▼                      │
                      ┌────────────────────┐           │
                      │ ready_to_cancel   │           │
                      └────────────────────┘           │
                                │                      │
                                ▼                      │
                   ┌──────────────────────────┐        │
                   │ cancellation_initiated   │        │
                   │ (sets initiated_at)      │        │
                   └──────────────────────────┘        │
                                │                      │
                                ▼                      │
                  ┌───────────────────────────┐        │
                  │ awaiting_confirmation     │        │
                  └───────────────────────────┘        │
                                │                      │
                                ▼                      │
                        ┌──────────────┐               │
                        │  completed   │               │
                        │ (FINAL STATE)│               │
                        └──────────────┘               │
                                                       │
              ┌──────────────────────────────────────┬─┘
              │                                      │
              ▼                                      ▼
      ┌──────────────┐                      ┌──────────────┐
      │   failed     │                      │  abandoned   │
      │              │                      │              │
      └──────────────┘                      └──────────────┘
       (can retry)                           (can reconsider)
```

### State Descriptions

| State | Description | Allowed Transitions | Timestamp Set |
|-------|-------------|---------------------|---------------|
| **considering** | User evaluating whether to cancel | researching, abandoned | - |
| **researching** | Investigating cancellation process | ready_to_cancel, abandoned | - |
| **ready_to_cancel** | Has instructions, ready to proceed | cancellation_initiated, abandoned | - |
| **cancellation_initiated** | User started cancellation process | awaiting_confirmation, completed, failed | cancellation_initiated_at |
| **awaiting_confirmation** | Waiting for provider confirmation | completed, failed | - |
| **completed** | Cancellation confirmed complete | FINAL - no transitions | cancellation_completed_at |
| **failed** | Cancellation attempt failed | researching, abandoned | - |
| **abandoned** | User decided not to cancel | considering (restart) | - |

### State Transition Rules

**Forward Progress:**
```
considering → researching → ready_to_cancel → cancellation_initiated → completed
```

**Exit Points (any state):**
```
any_state → abandoned
any_state → failed
```

**Immutable States:**
- `completed` - Once reached, no further transitions allowed
- Timestamps `cancellation_initiated_at` and `cancellation_completed_at` are immutable

**Automatic Behaviors:**
- Status change to `cancellation_initiated` → Sets `cancellation_initiated_at` timestamp
- Status change to `completed` → Sets `cancellation_completed_at` timestamp
- Timestamps can only be set once (immutable after first set)

---

## Data Flow Diagrams

### Review Suggestions Algorithm

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUGGESTION GENERATION                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              Query user's active subscriptions
                              │
                              ▼
          ┌───────────────────────────────────────┐
          │  For each subscription, analyze:      │
          │  1. Trial status                      │
          │  2. Email activity                    │
          │  3. Pricing history                   │
          │  4. Duplicate detection               │
          └───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TRIAL ANALYSIS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  IF trial_end_date exists:                                       │
│    IF trial_end_date == today:                                   │
│      → Priority: CRITICAL                                        │
│      → Reason: trial_ending                                      │
│      → Message: "Trial ends today. Cancel to avoid charges."     │
│      → Action Date: today                                        │
│                                                                  │
│    ELSE IF trial_end_date <= today + 3 days:                     │
│      → Priority: HIGH                                            │
│      → Reason: trial_ending_soon                                 │
│      → Message: "Trial ends in X days."                          │
│      → Action Date: trial_end_date                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ACTIVITY ANALYSIS                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Calculate: days_since_last_email                                │
│                                                                  │
│  IF days_since_last_email >= 30 AND amount > $20:                │
│    → Priority: HIGH                                              │
│    → Reason: expensive_unused                                    │
│    → Message: "High cost + no activity for 30+ days."            │
│                                                                  │
│  ELSE IF days_since_last_email >= 60:                            │
│    → Priority: MEDIUM                                            │
│    → Reason: likely_unused                                       │
│    → Message: "No activity for 60+ days."                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DUPLICATE DETECTION                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Group subscriptions by provider name                            │
│                                                                  │
│  IF count > 1 for same provider:                                 │
│    → Priority: CRITICAL                                          │
│    → Reason: duplicate_detected                                  │
│    → Message: "Multiple subscriptions to same provider."         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PRICING ANALYSIS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Compare: current_amount vs historical_amount                    │
│                                                                  │
│  IF price_increase detected:                                     │
│    → Priority: MEDIUM                                            │
│    → Reason: price_increased                                     │
│    → Message: "Price increased from $X to $Y."                   │
│    → Price Change Amount: difference                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Sort by priority:
                    1. CRITICAL
                    2. HIGH
                    3. MEDIUM
                    4. LOW
                              │
                              ▼
                    Return suggestions list
```

### Cancellation Research Flow

```
┌─────────────────────────────────────────────────────────────────┐
│             CANCELLATION RESEARCH REQUEST                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              POST /api/cancellation/research
              {
                "provider_name": "Netflix",
                "force_refresh": false
              }
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CACHE CHECK                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Query: provider_cancellation_info table                         │
│  WHERE: provider_name = "Netflix"                                │
│                                                                  │
│  IF force_refresh == false:                                      │
│    Check if record exists                                        │
│    Check if created_at < 30 days ago                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                 ┌────────────┴─────────────┐
                 │                          │
            Cache Hit?                  Cache Miss?
         (and not expired)           (or force_refresh)
                 │                          │
                 ▼                          ▼
        Return cached data         ┌─────────────────┐
                 │                 │  OPENAI REQUEST  │
                 │                 └─────────────────┘
                 │                          │
                 │                          ▼
                 │          OpenAI GPT-4 API Call
                 │          Prompt: "Research cancellation
                 │                   procedure for {provider}"
                 │                          │
                 │                          ▼
                 │          AI generates:
                 │          - Cancellation URL
                 │          - Difficulty rating
                 │          - Step-by-step instructions
                 │          - Requirements (phone/chat)
                 │          - Pause options
                 │          - Time estimate
                 │          - Gotchas & warnings
                 │          - Confidence score
                 │                          │
                 │                          ▼
                 │          ┌─────────────────────────┐
                 │          │  STORE IN DATABASE      │
                 │          └─────────────────────────┘
                 │                          │
                 │                          ▼
                 │          INSERT INTO provider_cancellation_info
                 │          - Cache for 30 days
                 │          - is_ai_generated = true
                 │          - is_verified = false
                 │                          │
                 └────────────┬─────────────┘
                              │
                              ▼
                      Return response
                      (cached or fresh)
```

### Status Update Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    STATUS UPDATE REQUEST                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
      PATCH /api/subscriptions/{id}/cancellation/status
      {
        "status": "cancellation_initiated",
        "notes": "Started cancellation process"
      }
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AUTHORIZATION CHECK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Verify JWT token                                             │
│  2. Check subscription belongs to authenticated user             │
│  3. Return 404 if not found or not authorized                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDATION                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Validate status value (must be in allowed enum)              │
│  2. Check if current status allows transition                    │
│  3. Return 400 if invalid                                        │
│  4. Return 409 if completed (no changes allowed)                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TIMESTAMP LOGIC                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  IF new_status == "cancellation_initiated":                      │
│    IF cancellation_initiated_at is NULL:                         │
│      SET cancellation_initiated_at = NOW()                       │
│                                                                  │
│  IF new_status == "completed":                                   │
│    IF cancellation_completed_at is NULL:                         │
│      SET cancellation_completed_at = NOW()                       │
│                                                                  │
│  Note: Timestamps are immutable once set                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Update database record:
                    - status
                    - notes (if provided)
                    - timestamps (if applicable)
                    - updated_at = NOW()
                              │
                              ▼
                    Return updated record
                    with provider_info included
```

---

## Integration Points

### Frontend → Backend API

**Authentication:**
```
All API requests require:
Authorization: Bearer {jwt_token}
```

**Review Dashboard:**
```javascript
// GET /api/reviews/suggestions
const { data } = useQuery({
  queryKey: ['reviewSuggestions'],
  queryFn: () => reviewsAPI.getSuggestions(acknowledged: false),
  refetchInterval: 5 * 60 * 1000, // 5 minutes
})
```

**Cancellation Research:**
```javascript
// POST /api/cancellation/research
const { mutate } = useMutation({
  mutationFn: (providerName) =>
    cancellationAPI.research(providerName, false),
  onSuccess: (data) => {
    // Display instructions
  },
})
```

**Status Updates:**
```javascript
// PATCH /api/subscriptions/{id}/cancellation/status
const { mutate } = useMutation({
  mutationFn: ({ status, notes }) =>
    cancellationAPI.updateStatus(subscriptionId, status, notes),
  onSuccess: () => {
    // Refresh data
  },
})
```

### Backend → OpenAI

**API Configuration:**
```python
import openai
from app.config import settings

openai.api_key = settings.OPENAI_API_KEY

# GPT-4 model for cancellation research
model = "gpt-4"
```

**Research Prompt:**
```python
prompt = f"""
Research the cancellation procedure for {provider_name}.
Provide:
1. Direct cancellation URL
2. Difficulty rating (easy/medium/hard)
3. Step-by-step instructions
4. Whether phone call or chat is required
5. If pause/downgrade options exist
6. Estimated time to complete
7. Common gotchas or important notes

Format as JSON.
"""
```

### Backend → Database

**SQLAlchemy Models:**
```python
class ProviderCancellationInfo(Base):
    __tablename__ = "provider_cancellation_info"

    id = Column(UUID, primary_key=True)
    provider_name = Column(String, unique=True, nullable=False)
    cancellation_url = Column(String)
    difficulty_rating = Column(String)
    instructions = Column(JSONB)  # List[str]
    # ... additional fields

class SubscriptionCancellationInfo(Base):
    __tablename__ = "subscription_cancellation_info"

    id = Column(UUID, primary_key=True)
    subscription_id = Column(UUID, ForeignKey("subscriptions.id"))
    status = Column(String, nullable=False)
    cancellation_initiated_at = Column(DateTime)
    cancellation_completed_at = Column(DateTime)
    # ... additional fields
```

---

## Error Handling

### Frontend Error Handling

**Network Errors:**
```typescript
if (error) {
  return (
    <Alert status="error">
      <AlertIcon />
      Failed to load suggestions. Please try again.
    </Alert>
  )
}
```

**Empty States:**
```typescript
if (filteredSuggestions.length === 0) {
  return (
    <Box textAlign="center">
      <Heading size="lg">All good! 🎉</Heading>
      <Text>No subscriptions need attention.</Text>
    </Box>
  )
}
```

### Backend Error Handling

**Authentication Errors:**
```python
# 401 Unauthorized
if not current_user:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated"
    )
```

**Authorization Errors:**
```python
# 404 Not Found (security - don't reveal existence)
subscription = get_subscription(subscription_id, user_id)
if not subscription:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Subscription not found"
    )
```

**Validation Errors:**
```python
# 400 Bad Request
if status not in ALLOWED_STATUSES:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid status value: {status}"
    )
```

**State Transition Errors:**
```python
# 409 Conflict
if cancellation_info.status == "completed":
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Cannot modify completed cancellation"
    )
```

**OpenAI API Errors:**
```python
# 500 Internal Server Error
try:
    response = await openai_client.chat.completions.create(...)
except Exception as e:
    logger.error(f"OpenAI API error: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to research cancellation for {provider_name}"
    )
```

### Error Recovery Strategies

**Frontend Retry Logic:**
```typescript
const { refetch } = useQuery({
  queryKey: ['reviewSuggestions'],
  queryFn: fetchSuggestions,
  retry: 3,
  retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
})
```

**Cache Fallback:**
```python
# If OpenAI fails, return cached data even if expired
try:
    ai_result = await research_with_ai(provider_name)
except Exception as e:
    cached = get_cached_provider_info(provider_name)
    if cached:
        logger.warning("Using expired cache due to AI failure")
        return cached
    raise e
```

**User Guidance:**
```typescript
// If AI research fails
<Alert status="warning">
  <AlertIcon />
  Could not research cancellation instructions automatically.
  Please visit the provider's website directly.
</Alert>
```

---

## Performance Considerations

### Caching Strategy

**Provider Research Cache:**
- Duration: 30 days
- Invalidation: Manual or on verification failure
- Benefit: Reduces OpenAI API costs, improves response time

**Query Optimization:**
```python
# Efficient suggestion generation
# Single query with joins instead of N+1
suggestions = (
    db.query(Subscription)
    .join(EmailAccount)
    .filter(Subscription.user_id == user_id)
    .options(selectinload(Subscription.email_account))
    .all()
)
```

**Frontend Caching:**
```typescript
// TanStack Query automatic caching
const { data } = useQuery({
  queryKey: ['reviewSuggestions'],
  queryFn: fetchSuggestions,
  staleTime: 5 * 60 * 1000, // 5 minutes
  cacheTime: 30 * 60 * 1000, // 30 minutes
})
```

### Rate Limiting

**OpenAI API:**
- Limit: 10 requests/minute per user
- Implementation: Redis-based rate limiter or in-memory cache
- Fallback: Return cached results when rate limited

**Frontend Debouncing:**
```typescript
// Prevent rapid filter changes
const debouncedFilter = useDebouncedValue(priorityFilter, 300)
```

---

## Security Considerations

### Data Privacy

**User Isolation:**
- All queries filtered by `user_id` from JWT token
- Subscriptions only accessible by owner
- Cancellation notes private to user

**Provider Info Sharing:**
- Provider research cached globally (no user-specific data)
- Only provider name sent to OpenAI
- No subscription amounts, emails, or user data in AI requests

### Input Validation

**Status Enum Validation:**
```python
ALLOWED_STATUSES = [
    "considering",
    "researching",
    "ready_to_cancel",
    "cancellation_initiated",
    "awaiting_confirmation",
    "completed",
    "failed",
    "abandoned"
]
```

**SQL Injection Protection:**
- SQLAlchemy ORM handles parameterization
- No raw SQL queries with user input

**XSS Protection:**
- React automatically escapes output
- Chakra UI components sanitize input

---

## Monitoring & Analytics

### Key Metrics to Track

**User Engagement:**
- Suggestions viewed per user
- Click-through rate on suggestion cards
- Cancellation instructions requested
- Status updates completed

**Cancellation Success:**
- Percentage reaching "completed" status
- Average time from "researching" to "completed"
- Failure rate and reasons

**System Performance:**
- API response times
- OpenAI API latency
- Cache hit rate
- Error rates by endpoint

**Cost Management:**
- OpenAI API calls per day
- Cache effectiveness (calls saved)
- Average cost per research request

---

## Future Enhancements

### Planned Features

1. **Email Notifications:**
   - Alert users when critical suggestions appear
   - Reminder emails for pending cancellations

2. **Calendar Integration:**
   - Add trial end dates to user's calendar
   - Cancellation deadline reminders

3. **Comparison Shopping:**
   - Suggest cheaper alternatives
   - Price comparison for similar services

4. **Bulk Actions:**
   - Cancel multiple subscriptions at once
   - Bulk status updates

5. **Analytics Dashboard:**
   - Total savings over time
   - Cancellation success metrics
   - Subscription spending trends

6. **Provider Verification:**
   - Community verification of AI instructions
   - User feedback on accuracy
   - Flag outdated information

---

**Version:** 1.0.0
**Last Updated:** January 2025
**Maintained By:** Subscription Tracker Team
