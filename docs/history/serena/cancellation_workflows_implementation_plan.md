# Cancellation Workflows - Implementation Plan

## Feature Overview
Help users actually cancel subscriptions with AI-powered cancellation research, step-by-step instructions, difficulty ratings, and smart review suggestions.

## Implementation Phases

### Phase 1: Database Schema & Migrations
**Goal**: Create data models to store cancellation information

**Tasks:**
1. Create `provider_cancellation_info` table
   - Fields: id, provider_name, cancellation_url, difficulty_rating, instructions, instructions_source, requires_phone_call, requires_chat, allows_pause, pause_instructions, last_verified_at, ai_research_prompt, ai_research_response, created_at, updated_at
   - Indexes: provider_name (unique), difficulty_rating, last_verified_at

2. Update `subscriptions` table
   - Add fields: cancellation_status (enum), cancellation_requested_at, cancellation_confirmed_at, cancellation_notes
   - Add index on cancellation_status

3. Create Alembic migration
   - Write upgrade() and downgrade() functions
   - Test migration on development database

**Files to Create:**
- `backend/alembic/versions/YYYY_MM_DD_add_cancellation_workflows.py`

**Files to Modify:**
- `backend/app/models/subscription.py` - Add cancellation fields
- `backend/app/models/cancellation.py` - NEW model for provider_cancellation_info

**Acceptance Criteria:**
- ✅ Migration runs successfully
- ✅ Tables created with correct schema
- ✅ Can rollback migration cleanly
- ✅ Models have proper relationships and validations

---

### Phase 2: AI Cancellation Research Service
**Goal**: Use OpenAI to research how to cancel unknown subscription services

**Tasks:**
1. Create `CancellationResearchService` class
   - Method: `research_provider(provider_name: str) -> dict`
   - Use OpenAI GPT-4o-mini for cost efficiency
   - Structure prompt to get JSON output
   - Parse and validate AI response

2. Implement caching logic
   - Check if provider already researched (database lookup)
   - Return cached results if < 90 days old
   - Store research results in database

3. Add confidence scoring
   - AI indicates confidence level (0.0 to 1.0)
   - Flag low-confidence results for manual review
   - Track research success/failure rates

4. Error handling
   - Handle OpenAI API failures gracefully
   - Fallback to basic instructions if AI fails
   - Log all research attempts for debugging

**Files to Create:**
- `backend/app/services/cancellation_research.py` - NEW service
- `backend/app/schemas/cancellation.py` - NEW Pydantic schemas

**Files to Modify:**
- `backend/app/services/ai_classifier.py` - May reuse OpenAI client setup

**AI Prompt Template:**
```
Research how to cancel a {provider_name} subscription.

Provide the following information:
1. Direct cancellation URL (if available)
2. Step-by-step cancellation instructions (detailed)
3. Difficulty rating: easy (1-click), medium (multiple steps), hard (phone/chat required)
4. Does it require a phone call? (yes/no)
5. Does it require live chat? (yes/no)
6. Can you pause instead of cancel? (yes/no)
7. Pause instructions (if applicable)
8. Important notes (e.g., timing requirements, refund policies)
9. Confidence score (0.0-1.0) for accuracy of this information

Return as JSON with keys: cancellation_url, instructions (array), difficulty, requires_phone, requires_chat, allows_pause, pause_instructions (array), notes, confidence
```

**Acceptance Criteria:**
- ✅ Can research cancellation info for any provider
- ✅ Returns structured, validated data
- ✅ Caches results to avoid duplicate API calls
- ✅ Handles errors gracefully
- ✅ Logs all research activity

---

### Phase 3: Backend API Endpoints
**Goal**: Create REST API for cancellation workflow operations

**Tasks:**
1. Cancellation info endpoints
   - `GET /api/subscriptions/{id}/cancellation-info` - Get cached or research new
   - `POST /api/subscriptions/{id}/research-cancellation` - Force AI research
   - `GET /api/cancellation-providers` - List all known providers
   - `GET /api/cancellation-providers/{provider_name}` - Get specific provider info

2. Cancellation status endpoints
   - `PATCH /api/subscriptions/{id}/cancellation-status` - Update status
   - `GET /api/subscriptions/pending-cancellation` - List pending cancellations

3. Review suggestions endpoint
   - `GET /api/subscriptions/review-suggestions` - Smart recommendations
   - Logic: trials ending, unused (no emails 90+ days), price increases, expensive+unused

4. Admin endpoints (optional)
   - `PUT /api/admin/cancellation-providers/{provider_name}` - Manually add/update
   - `POST /api/admin/cancellation-providers/{provider_name}/verify` - Mark as verified

**Files to Create:**
- `backend/app/api/cancellation.py` - NEW API router

**Files to Modify:**
- `backend/app/api/__init__.py` - Register cancellation router
- `backend/app/schemas/subscription.py` - Add cancellation status schemas

**Acceptance Criteria:**
- ✅ All endpoints return proper status codes
- ✅ Input validation with Pydantic
- ✅ Proper error messages
- ✅ Authentication/authorization enforced
- ✅ API documented with docstrings

---

### Phase 4: Review Suggestions Algorithm
**Goal**: Intelligently identify subscriptions users should consider canceling

**Tasks:**
1. Implement scoring algorithm
   - Trial ending soon (3-7 days): HIGH priority
   - Trial ending today: CRITICAL priority
   - No emails in 90+ days: MEDIUM priority
   - Price increase in last 30 days: MEDIUM priority
   - Expensive (>$30) + no emails 60+ days: HIGH priority
   - Duplicate subscriptions detected: HIGH priority

2. Create suggestion categories
   - "Trial Ending" - Act now to avoid charges
   - "Likely Unused" - No activity detected
   - "Price Increased" - Cost went up recently
   - "High Cost" - Expensive subscription with low usage
   - "Duplicate Detected" - Similar service subscribed twice

3. Add user preferences
   - Allow users to dismiss suggestions
   - Track dismissals to avoid re-suggesting
   - "Snooze" option (remind in X days)

**Files to Create:**
- `backend/app/services/review_suggestions.py` - NEW service

**Files to Modify:**
- `backend/app/models/subscription.py` - May need suggestion_dismissed_at field

**Acceptance Criteria:**
- ✅ Identifies relevant subscriptions accurately
- ✅ Prioritizes suggestions correctly
- ✅ Respects user dismissals
- ✅ Performant (< 500ms for 100+ subscriptions)

---

### Phase 5: Frontend - Cancellation Info Display
**Goal**: Show cancellation instructions on subscription detail page

**Tasks:**
1. Create `CancellationTab` component
   - Show difficulty badge (🟢 Easy / 🟡 Medium / 🔴 Hard)
   - Display direct cancellation link (if available)
   - Show step-by-step instructions
   - Option to pause instead of cancel
   - "Mark as Cancelled" button
   - Cancellation notes textarea

2. Add "Research with AI" button
   - Shown when no cancellation info exists
   - Triggers AI research API call
   - Shows loading state during research
   - Displays confidence score after research

3. Create `CancellationStatusBadge` component
   - Visual indicator: Active / Pending / Paused / Cancelled
   - Show on subscription cards and detail page

4. Add quick action menu item
   - "How to Cancel" option in subscription card menu
   - Opens modal with cancellation info

**Files to Create:**
- `frontend/src/components/subscriptions/CancellationTab.tsx` - NEW component
- `frontend/src/components/subscriptions/CancellationStatusBadge.tsx` - NEW component
- `frontend/src/api/cancellation.ts` - NEW API client methods

**Files to Modify:**
- `frontend/src/components/subscriptions/SubscriptionDetail.tsx` - Add cancellation tab
- `frontend/src/components/subscriptions/SubscriptionCard.tsx` - Add status badge

**Acceptance Criteria:**
- ✅ Clean, intuitive UI
- ✅ Mobile responsive
- ✅ Loading states for AI research
- ✅ Error handling with user-friendly messages
- ✅ Accessible (ARIA labels, keyboard navigation)

---

### Phase 6: Frontend - Review Suggestions Dashboard
**Goal**: Proactive dashboard widget suggesting subscriptions to review

**Tasks:**
1. Create `ReviewSuggestions` component
   - Card-based layout with categories
   - Priority indicators (🔴 Critical, 🟡 Important, 🔵 Info)
   - Quick actions: "View Details", "Dismiss", "Snooze"
   - Empty state: "No subscriptions need review 🎉"

2. Add to Dashboard
   - Position prominently (top of page or sidebar)
   - Collapsible if no critical suggestions
   - Show count badge: "3 subscriptions need review"

3. Implement suggestion actions
   - Dismiss: Hide permanently with confirmation
   - Snooze: Remind in 7/14/30 days
   - View Details: Navigate to subscription with cancellation tab open

**Files to Create:**
- `frontend/src/components/dashboard/ReviewSuggestions.tsx` - NEW component
- `frontend/src/components/dashboard/SuggestionCard.tsx` - NEW component

**Files to Modify:**
- `frontend/src/pages/Dashboard.tsx` - Add ReviewSuggestions widget
- `frontend/src/api/subscriptions.ts` - Add getReviewSuggestions() method

**Acceptance Criteria:**
- ✅ Visually distinct priority levels
- ✅ Clear, actionable messaging
- ✅ Smooth dismiss/snooze interactions
- ✅ Updates in real-time after actions
- ✅ Doesn't clutter dashboard when no suggestions

---

### Phase 7: Testing & Refinement
**Goal**: Ensure feature works reliably across scenarios

**Tasks:**
1. Backend unit tests
   - CancellationResearchService with mocked OpenAI
   - Review suggestions algorithm accuracy
   - API endpoint validation

2. Frontend component tests
   - CancellationTab rendering
   - AI research button interaction
   - Dismiss/snooze actions

3. Integration tests
   - End-to-end: Request research → Display results → Update status
   - Review suggestions → View detail → Cancel workflow

4. Manual testing scenarios
   - Test with real subscription providers
   - Verify AI research accuracy (spot-check 10 providers)
   - Test mobile responsiveness
   - Accessibility audit

5. Performance optimization
   - Cache AI research results
   - Optimize review suggestions query
   - Lazy load cancellation info

**Files to Create:**
- `backend/tests/test_cancellation_research.py`
- `backend/tests/test_review_suggestions.py`
- `frontend/src/components/subscriptions/__tests__/CancellationTab.test.tsx`

**Acceptance Criteria:**
- ✅ >80% code coverage
- ✅ All critical paths tested
- ✅ No console errors or warnings
- ✅ Lighthouse accessibility score >90
- ✅ Review suggestions return in <500ms

---

### Phase 8: Documentation & Deployment
**Goal**: Document feature and deploy to production

**Tasks:**
1. Update API documentation
   - Document all cancellation endpoints
   - Add example requests/responses
   - Note OpenAI API key requirement

2. User documentation
   - How-to guide: "Using Cancellation Workflows"
   - FAQ: "How accurate is AI research?"
   - Privacy note: "We don't share your data with providers"

3. Admin documentation
   - How to manually verify cancellation info
   - How to update provider instructions
   - Monitoring AI research costs

4. Deployment checklist
   - Run database migrations
   - Verify OpenAI API key configured
   - Test on staging environment
   - Monitor error rates after deployment

**Files to Create:**
- `backend/claudedocs/cancellation_workflows_architecture.md`
- `backend/claudedocs/cancellation_workflows_api.md`

**Files to Update:**
- `ROADMAP.md` - Mark cancellation workflows as complete

**Acceptance Criteria:**
- ✅ All documentation complete
- ✅ Migrations run successfully in production
- ✅ No errors in production logs (first 24 hours)
- ✅ Feature flag enabled for all users

---

## Risk Mitigation

**Risk 1: AI Research Inaccuracy**
- Mitigation: Add confidence scores, manual verification flag
- Fallback: Show generic "contact provider" instructions

**Risk 2: Provider Policy Changes**
- Mitigation: Auto-refresh research every 90 days
- User feedback: "Report outdated info" button

**Risk 3: OpenAI API Costs**
- Mitigation: Cache all results, use GPT-4o-mini (cheaper)
- Monitoring: Alert if daily costs exceed threshold

**Risk 4: Legal/Compliance**
- Mitigation: Disclaimer: "Instructions for informational purposes only"
- No automated cancellation (user must do it themselves)

---

## Success Metrics

**Technical Metrics:**
- AI research accuracy: >85% confidence score average
- API response time: <1 second for cached results
- Feature adoption: >30% of users view cancellation info

**User Metrics:**
- Cancellation success rate: Track via status updates
- Review suggestion engagement: >40% click-through rate
- User satisfaction: Positive feedback on cancellation ease

**Business Metrics:**
- Feature usage: Track cancellation info views per week
- Cost efficiency: Monitor OpenAI API spend per research
- User retention: Feature contributes to perceived value

---

## Next Steps
1. Start with Phase 1: Database schema and migrations
2. Validate schema with user before proceeding
3. Implement Phase 2: AI research service (the core innovation)
4. Get early feedback on AI research quality
5. Continue phases 3-8 sequentially
