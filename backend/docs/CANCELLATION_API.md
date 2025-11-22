# Cancellation Workflows API Documentation

Complete API documentation for the cancellation workflows feature implemented in Phase 1-6.

## Table of Contents
1. [Review Suggestions API](#review-suggestions-api)
2. [Cancellation Research API](#cancellation-research-api)
3. [Cancellation Status Management API](#cancellation-status-management-api)
4. [Data Models](#data-models)

---

## Review Suggestions API

AI-powered subscription review suggestions based on usage patterns, pricing, and trial status.

### Get Review Suggestions

**Endpoint:** `GET /api/reviews/suggestions`

**Authentication:** Required (Bearer token)

**Query Parameters:**
- `acknowledged` (boolean, optional): Filter by acknowledgment status
  - `true`: Only acknowledged suggestions
  - `false`: Only unacknowledged suggestions
  - Not provided: All suggestions

**Response:** `200 OK`

```json
{
  "total_count": 5,
  "critical_count": 2,
  "high_priority_count": 1,
  "suggestions": [
    {
      "subscription_id": "uuid",
      "provider": "Netflix",
      "amount": 15.99,
      "currency": "USD",
      "billing_cycle": "monthly",
      "priority": "critical",
      "reason": "trial_ending",
      "message": "Your trial ends today. Cancel now to avoid being charged.",
      "action_by_date": "2025-01-19",
      "days_since_last_email": 30,
      "price_change_amount": null,
      "acknowledged_at": null
    }
  ]
}
```

**Priority Levels:**
- `critical`: Immediate action required (trial ending today, duplicate charges)
- `high`: Important action within days (trial ending soon, expensive unused)
- `medium`: Review recommended (likely unused, price increased)
- `low`: Optional review (general optimization)

**Reason Codes:**
- `trial_ending`: Trial ends today
- `trial_ending_soon`: Trial ends within 3 days
- `expensive_unused`: High cost + no activity for 30+ days
- `likely_unused`: No activity for 60+ days
- `duplicate_detected`: Multiple subscriptions to same provider
- `price_increased`: Recent price increase detected

**Algorithm Logic:**
- Checks trial end dates against current date
- Analyzes last email activity timestamp
- Compares current vs historical pricing
- Detects duplicate providers per user
- Assigns priority based on urgency and financial impact

---

## Cancellation Research API

AI-powered research of cancellation procedures using OpenAI GPT-4.

### Research Provider Cancellation

**Endpoint:** `POST /api/cancellation/research`

**Authentication:** Required (Bearer token)

**Request Body:**

```json
{
  "provider_name": "Netflix",
  "force_refresh": false
}
```

**Parameters:**
- `provider_name` (string, required): Name of the service provider
- `force_refresh` (boolean, optional, default: false): Force new AI research even if cached

**Response:** `200 OK`

```json
{
  "provider_name": "Netflix",
  "cancellation_url": "https://www.netflix.com/cancelplan",
  "difficulty_rating": "easy",
  "instructions": [
    "Log in to your Netflix account",
    "Go to Account settings",
    "Click 'Cancel Membership'",
    "Confirm cancellation"
  ],
  "requires_phone_call": false,
  "requires_chat": false,
  "allows_pause": true,
  "pause_instructions": [
    "Go to Account settings",
    "Select 'Pause Membership'",
    "Choose pause duration (1-3 months)"
  ],
  "estimated_time_minutes": 5,
  "cancellation_gotchas": [
    "Cancellation takes effect at end of billing period",
    "Download history before cancelling if needed"
  ],
  "additional_notes": "Netflix makes cancellation straightforward with no retention tactics.",
  "ai_confidence_score": 0.95
}
```

**Difficulty Ratings:**
- `easy`: Self-service online, < 5 minutes
- `medium`: Multiple steps or chat required, 5-15 minutes
- `hard`: Phone call required or complex process, 15+ minutes

**AI Research Process:**
1. Searches provider's official cancellation documentation
2. Analyzes user experience reports and reviews
3. Identifies common pitfalls and gotchas
4. Generates step-by-step instructions
5. Estimates difficulty and time requirements
6. Confidence scoring based on source quality

**Caching Strategy:**
- Results cached for 30 days unless `force_refresh=true`
- Cache invalidated on provider verification failures
- Confidence score < 0.6 triggers auto-refresh after 7 days

**Error Responses:**

```json
// 400 Bad Request - Invalid provider name
{
  "detail": "Provider name is required"
}

// 500 Internal Server Error - AI research failed
{
  "detail": "Failed to research cancellation instructions for Netflix"
}
```

---

## Cancellation Status Management API

Track and manage cancellation status throughout the user journey.

### Get Subscription Cancellation Info

**Endpoint:** `GET /api/subscriptions/{subscription_id}/cancellation`

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `subscription_id` (uuid, required): Subscription ID

**Response:** `200 OK`

```json
{
  "id": "uuid",
  "subscription_id": "uuid",
  "status": "researching",
  "cancellation_initiated_at": null,
  "cancellation_completed_at": null,
  "notes": null,
  "created_at": "2025-01-19T10:00:00Z",
  "updated_at": "2025-01-19T10:00:00Z",
  "provider_info": {
    "id": "uuid",
    "provider_name": "Netflix",
    "cancellation_url": "https://www.netflix.com/cancelplan",
    "difficulty_rating": "easy",
    "instructions": ["Step 1", "Step 2"],
    "requires_phone_call": false,
    "requires_chat": false,
    "allows_pause": true,
    "pause_instructions": ["Pause step 1"],
    "estimated_time_minutes": 5,
    "cancellation_gotchas": ["Gotcha 1"],
    "additional_notes": "Notes",
    "ai_confidence_score": 0.95,
    "is_ai_generated": true,
    "is_verified": false,
    "needs_reverification": false
  }
}
```

**Status Values:**
- `considering`: User is evaluating whether to cancel
- `researching`: Investigating cancellation process
- `ready_to_cancel`: Has instructions, ready to proceed
- `cancellation_initiated`: User started cancellation process
- `awaiting_confirmation`: Waiting for provider confirmation
- `completed`: Cancellation confirmed complete
- `failed`: Cancellation attempt failed
- `abandoned`: User decided not to cancel

### Update Cancellation Status

**Endpoint:** `PATCH /api/subscriptions/{subscription_id}/cancellation/status`

**Authentication:** Required (Bearer token)

**Request Body:**

```json
{
  "status": "cancellation_initiated",
  "notes": "Started cancellation process via website"
}
```

**Parameters:**
- `status` (enum, required): New status value
- `notes` (string, optional): Additional notes about the status change

**Response:** `200 OK`

Returns updated cancellation info object (same as GET endpoint).

**Automatic Timestamp Management:**
- `cancellation_initiated_at`: Set when status changes to `cancellation_initiated`
- `cancellation_completed_at`: Set when status changes to `completed`
- Both timestamps can only be set once (immutable after first set)

**Business Rules:**
1. Status can only progress forward in most cases:
   - `considering` → `researching` → `ready_to_cancel` → `cancellation_initiated` → `completed`
2. Can jump to `abandoned` or `failed` from any status
3. Once `completed`, status cannot be changed
4. Timestamps are auto-managed, cannot be set manually

**Error Responses:**

```json
// 404 Not Found - Subscription not found or not owned by user
{
  "detail": "Subscription not found"
}

// 400 Bad Request - Invalid status value
{
  "detail": "Invalid status value"
}

// 409 Conflict - Completed cancellation cannot be modified
{
  "detail": "Cannot modify completed cancellation"
}
```

---

## Data Models

### ReviewSuggestion

```python
class ReviewSuggestion(BaseModel):
    subscription_id: UUID
    provider: str
    amount: Optional[float]
    currency: str
    billing_cycle: str
    priority: str  # critical, high, medium, low
    reason: str  # trial_ending, trial_ending_soon, etc.
    message: str
    action_by_date: Optional[date]
    days_since_last_email: Optional[int]
    price_change_amount: Optional[float]
    acknowledged_at: Optional[datetime]
```

### ProviderCancellationInfo

```python
class ProviderCancellationInfo(BaseModel):
    id: UUID
    provider_name: str
    cancellation_url: Optional[str]
    difficulty_rating: str  # easy, medium, hard
    instructions: List[str]
    requires_phone_call: bool
    requires_chat: bool
    allows_pause: bool
    pause_instructions: Optional[List[str]]
    estimated_time_minutes: Optional[int]
    cancellation_gotchas: Optional[List[str]]
    additional_notes: Optional[str]
    ai_confidence_score: Optional[float]
    is_ai_generated: bool
    is_verified: bool
    needs_reverification: bool
    created_at: datetime
    updated_at: datetime
```

### SubscriptionCancellationInfo

```python
class SubscriptionCancellationInfo(BaseModel):
    id: UUID
    subscription_id: UUID
    status: str  # considering, researching, ready_to_cancel, etc.
    cancellation_initiated_at: Optional[datetime]
    cancellation_completed_at: Optional[datetime]
    notes: Optional[str]
    provider_info: Optional[ProviderCancellationInfo]
    created_at: datetime
    updated_at: datetime
```

---

## Rate Limits & Quotas

### OpenAI API Usage
- **Rate Limit**: Respects OpenAI tier limits
- **Cost Optimization**: Results cached for 30 days
- **Fallback**: Returns cached partial data if API fails

### Endpoint Rate Limits
- Review Suggestions: 60 requests/minute per user
- Cancellation Research: 10 requests/minute per user (AI-heavy)
- Status Updates: 30 requests/minute per user

---

## Security Considerations

1. **Authentication**: All endpoints require valid JWT Bearer token
2. **Authorization**: Users can only access their own subscriptions
3. **Data Privacy**:
   - Cancellation notes are private to user
   - Provider research cached globally (no user-specific data)
4. **Input Validation**:
   - Provider names sanitized before AI research
   - Status values validated against enum
   - SQL injection protection via SQLAlchemy ORM

---

## Integration Examples

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000/api"
token = "your_jwt_token"
headers = {"Authorization": f"Bearer {token}"}

# Get review suggestions
response = requests.get(f"{BASE_URL}/reviews/suggestions", headers=headers)
suggestions = response.json()

# Research cancellation for a provider
research_data = {
    "provider_name": "Netflix",
    "force_refresh": False
}
response = requests.post(
    f"{BASE_URL}/cancellation/research",
    json=research_data,
    headers=headers
)
instructions = response.json()

# Update cancellation status
status_data = {
    "status": "cancellation_initiated",
    "notes": "Started cancellation process"
}
response = requests.patch(
    f"{BASE_URL}/subscriptions/{subscription_id}/cancellation/status",
    json=status_data,
    headers=headers
)
cancellation_info = response.json()
```

### JavaScript/TypeScript Example

```typescript
const BASE_URL = "http://localhost:8000/api";
const token = localStorage.getItem("access_token");
const headers = {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json"
};

// Get review suggestions
const suggestions = await fetch(`${BASE_URL}/reviews/suggestions`, { headers })
  .then(res => res.json());

// Research cancellation
const instructions = await fetch(`${BASE_URL}/cancellation/research`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    provider_name: "Netflix",
    force_refresh: false
  })
}).then(res => res.json());

// Update status
const cancellationInfo = await fetch(
  `${BASE_URL}/subscriptions/${subscriptionId}/cancellation/status`,
  {
    method: "PATCH",
    headers,
    body: JSON.stringify({
      status: "cancellation_initiated",
      notes: "Started cancellation process"
    })
  }
).then(res => res.json());
```

---

## Testing

### Manual API Testing with cURL

```bash
# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r '.access_token')

# Test review suggestions
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/reviews/suggestions | jq

# Test cancellation research
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/cancellation/research \
  -d '{"provider_name":"Netflix","force_refresh":false}' | jq

# Get cancellation info for subscription
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/subscriptions/SUBSCRIPTION_ID/cancellation | jq

# Update cancellation status
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/subscriptions/SUBSCRIPTION_ID/cancellation/status \
  -d '{"status":"cancellation_initiated","notes":"Started process"}' | jq
```

---

## Changelog

### Version 1.0.0 (Phase 1-6 Implementation)

**Added:**
- Review suggestions endpoint with AI-powered analysis
- Cancellation research endpoint with OpenAI integration
- Cancellation status management with state machine
- Provider cancellation info caching
- Priority-based suggestion sorting
- Multi-criteria review algorithm

**Database Changes:**
- `provider_cancellation_info` table
- `subscription_cancellation_info` table
- Status tracking with automatic timestamps

**Frontend Integration:**
- Review Dashboard page
- Cancellation tab in subscription details
- Real-time status updates
- Filter and search capabilities
