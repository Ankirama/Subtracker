# AI Sandbox Feature - Complete Implementation

## Overview
Built a complete AI Sandbox feature with two main sections:
1. **Manual Test** - Interactive testing for email classification and data extraction
2. **Review Uncertain Emails** - Workflow for validating low-confidence classifications

## Backend Implementation

### 1. API Schemas (`backend/app/schemas/ai_sandbox.py`)
Created comprehensive request/response schemas:
- `EmailTestRequest` - Input for testing email content
- `ClassificationTestResponse` - Classification results with confidence and reasoning
- `ExtractionTestResponse` - Extracted subscription data with raw AI response
- `UncertainEmail` - Summary of emails needing review
- `UncertainEmailsResponse` - List response with statistics
- `EmailDetailResponse` - Detailed email view for review
- `ManualSubscriptionCreate` - Manual subscription creation from reviewed email

### 2. API Endpoints (`backend/app/api/ai_sandbox.py`)
Implemented 5 endpoints:

**POST `/api/ai-sandbox/test-classification`**
- Test email classification without saving to database
- Returns: is_subscription, confidence, reasoning, category

**POST `/api/ai-sandbox/test-extraction`**
- Test subscription data extraction without saving
- Returns: provider, amount, currency, billing_cycle, renewal_date, etc.

**GET `/api/ai-sandbox/uncertain-emails`**
- List emails needing review (low confidence < 0.8 OR no subscription created)
- Returns: emails list with statistics (uncertain_classified, extraction_failed)

**GET `/api/ai-sandbox/email/{email_id}`**
- Get detailed email information for review
- Returns: full email content, classification reasoning, linked subscription status

**POST `/api/ai-sandbox/create-subscription`**
- Manually create subscription from reviewed email
- Validates uniqueness (provider + custom_label)
- Returns: success, subscription_id, message

### 3. Router Registration (`backend/app/main.py`)
Registered AI Sandbox router at `/api/ai-sandbox` prefix

## Frontend Implementation

### 1. TypeScript Types (`frontend/src/types/index.ts`)
Added all AI Sandbox types matching backend schemas

### 2. API Client (`frontend/src/api/aiSandbox.ts`)
Created API client with 5 methods corresponding to backend endpoints

### 3. Main Page Component (`frontend/src/components/ai-sandbox/AISandboxPage.tsx`)
- Two-tab layout using Chakra UI Tabs
- Tab 1: Manual Test
- Tab 2: Review Uncertain Emails

### 4. Manual Test Tab (`frontend/src/components/ai-sandbox/ManualTestTab.tsx`)
**Features:**
- Input form for email content (subject, sender, sender_name, body_text)
- Three test buttons: "Test Classification", "Test Extraction", "Test Both"
- Classification results display:
  - Is Subscription badge (YES/NO)
  - Confidence score with color coding (green ≥80%, yellow ≥60%, red <60%)
  - Category
  - AI reasoning explanation
- Extraction results display:
  - Confidence score
  - Provider, amount, currency, billing cycle, renewal date, custom label
  - Category
  - Extraction method
  - Raw AI response (JSON) for debugging

### 5. Review Emails Tab (`frontend/src/components/ai-sandbox/ReviewEmailsTab.tsx`)
**Features:**
- Statistics badges: Low Confidence count, Extraction Failed count
- Email list table with:
  - Subject, sender (name + email), date
  - Confidence badge (color-coded)
  - Status badge (Linked/No Subscription)
  - Review button for each email
- Email Detail Modal:
  - Full email content (subject, from, to, date, body)
  - Classification confidence and status
  - Classification reasoning (JSON)
  - "Create Subscription" button if not linked
- Create Subscription Modal:
  - Form for manual subscription creation
  - Fields: provider (required), amount, currency, billing cycle, renewal date, custom label, category, notes
  - Validates uniqueness (provider + custom_label)
  - Refreshes list after creation

### 6. Navigation (`frontend/src/App.tsx` + `frontend/src/components/common/DashboardLayout.tsx`)
- Added route: `/ai-sandbox` → `<AISandboxPage />`
- Added navigation link in sidebar with FiTool icon

## How to Use

### Manual Test Tab
1. Navigate to AI Sandbox from sidebar
2. Select "Manual Test" tab
3. Paste email content (subject and sender are required)
4. Click "Test Classification" to see if email is subscription-related
5. Click "Test Extraction" to extract subscription data
6. Click "Test Both" to run both tests
7. Review AI reasoning and extracted data

### Review Uncertain Emails Tab
1. Navigate to AI Sandbox from sidebar
2. Select "Review Uncertain Emails" tab
3. See list of emails with:
   - Low confidence (<80%)
   - Failed extraction (classified but no subscription created)
4. Click "Review" button on any email
5. Review full email content and classification reasoning
6. If email should be a subscription, click "Create Subscription"
7. Fill in subscription details manually
8. Submit to create subscription

## Benefits

1. **Iterative Prompt Improvement**: Test classification/extraction prompts without database changes
2. **Quality Assurance**: Review uncertain classifications before they become subscriptions
3. **Manual Correction**: Create subscriptions from emails that failed automatic extraction
4. **Debugging**: See raw AI responses and reasoning for troubleshooting
5. **Confidence Monitoring**: Track classification quality with confidence scores

## Technical Details

**Security:**
- All endpoints protected by authentication (requires current user)
- Email access validated against user's mailboxes
- Subscription uniqueness enforced (provider + custom_label)

**Performance:**
- No database writes for test endpoints
- Efficient queries for uncertain emails (indexed fields)
- Lazy loading with React Query for caching

**User Experience:**
- Color-coded confidence scores (green/yellow/red)
- Real-time feedback with toast notifications
- Modal workflows for detailed review
- Form validation before submission

## Status
✅ All features implemented and ready for testing
✅ Backend API endpoints operational (after restart)
✅ Frontend components integrated with navigation
✅ Ready for user testing and feedback
