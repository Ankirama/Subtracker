# API Conventions

> REST patterns, pagination, error responses, and request/response shapes. Endpoint-by-endpoint reference for the backend, plus frontend consumption patterns (React Query hooks, project structure).

## General Conventions

- All endpoints are prefixed with `/api/`.
- RESTful resource naming.
- Consistent error responses with `detail` messages.
- Pagination on list endpoints uses `page` (1-indexed) and `page_size`.
- Authentication via Bearer JWT in the `Authorization` header (see auth.md).
- Interactive OpenAPI docs at `http://localhost:8000/docs`.

## Pagination Shape

```json
{
  "subscriptions": [ /* … */ ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

## Authentication Endpoints

(See `auth.md` for the full endpoint reference, JWT payloads, password rules, and client integration.)

### POST /api/auth/register

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

### POST /api/auth/login

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

### POST /api/auth/refresh

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

## Mailbox Endpoints

### POST /api/mailboxes — Create/connect a new mailbox

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

### GET /api/mailboxes — List user's mailboxes

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

### POST /api/mailboxes/{mailbox_id}/test-connection

```json
Response: 200 OK
{
  "status": "success",
  "message": "Successfully connected to mailbox",
  "email_count": 15234
}
```

### PUT /api/mailboxes/{mailbox_id}
Update mailbox settings.

### DELETE /api/mailboxes/{mailbox_id}
Remove mailbox.

## Email Processing Endpoints

### POST /api/mailboxes/{mailbox_id}/import — Trigger email import/sync

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

### GET /api/jobs/{job_id} — Job status and progress

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

### GET /api/jobs/{job_id}/stream
WebSocket endpoint for real-time progress updates.

## Subscription Endpoints

### GET /api/subscriptions — List with filtering

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

### GET /api/subscriptions/{subscription_id}
Get subscription details.

### POST /api/subscriptions — Manually create

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

### PUT /api/subscriptions/{subscription_id}
Update subscription.

### DELETE /api/subscriptions/{subscription_id}
Delete subscription.

### GET /api/subscriptions/{subscription_id}/history
Get subscription change history.

## Email Review Endpoints

### GET /api/email-reviews/pending — Emails pending manual review (50–84 % confidence)

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

### GET /api/email-reviews/rejected
Rejected emails (<50 % confidence).

### POST /api/email-reviews/{record_id}/accept — Manually accept

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

### POST /api/email-reviews/{record_id}/reject
Manually reject an email.

### GET /api/email-reviews/{record_id}/email-content — Fetch full email

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

## Analytics Endpoints

### GET /api/analytics/spending-trends

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

### GET /api/analytics/category-breakdown

```json
Response: 200 OK
{
  "data": [
    {"category": "streaming", "total": 45.97, "count": 3},
    {"category": "software", "total": 89.97, "count": 5}
  ]
}
```

### GET /api/analytics/top-expensive

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

## Budget Endpoints

### GET /api/budgets
Get user budgets.

### POST /api/budgets — Create budget

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

### PUT /api/budgets/{budget_id}
Update budget.

### GET /api/budgets/status — Current budget status

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

## Settings Endpoints

### GET /api/settings
Get user settings.

### PUT /api/settings — Update settings

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

## Data Export Endpoints

### GET /api/export/subscriptions — Export all subscription data

```json
Query params:
- format: json|csv

Response: 200 OK (file download)
```

### DELETE /api/user/data
Delete all user data (GDPR compliance).

---

## Frontend Consumption

The frontend is a React + TypeScript SPA built with Vite, Chakra UI, React Query, Recharts, and Axios. This section captures the patterns clients use to consume the API.

### Project Structure

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

### Key React Query Hooks

```typescript
// useSubscriptions.ts
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

```typescript
// useImportProgress.ts
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

Notes:
- React Query staleTime defaults to 30 seconds.
- WebSocket reconnection logic is needed for long-running imports.
- Chakra UI requires its `ThemeProvider` wrapper at the root.

### Dashboard Layout

1. **Header**: navigation, user menu, settings.
2. **Sidebar**: quick stats, budget status, filters.
3. **Main Content**: subscription list with sort/filter; charts (spending trends, category breakdown); pending reviews count/link.
4. **Modals**: add subscription, edit subscription, view email.

### Frontend Test (excerpt)

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
