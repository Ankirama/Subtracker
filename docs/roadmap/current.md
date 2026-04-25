# Roadmap — Active

> See docs/_archive/roadmap-phase-1-completed.md for historical/completed items.
> See docs/roadmap/mobile.md for the mobile responsive roadmap.

This document tracks planned and in-progress features for the Subscription Tracker application.

---

## 🚀 In Progress

*Currently no features in progress - ready for next feature implementation!*

---

## 📋 Planned Features

### Subscription Insights & Analytics 📊

**Status:** Partially Complete
**Priority:** High
**Estimated Effort:** Medium

> Completed sub-items (price change history tracking, basic spending statistics) are recorded in
> docs/_archive/roadmap-phase-1-completed.md.

**Remaining Features:**
- [ ] Usage recommendations (suggest cancellations based on patterns)
- [ ] Cost comparisons (family plan vs individual)
- [ ] Advanced spending breakdown visualizations
- [ ] Year-over-year cost analysis
- [ ] Subscription lifecycle analytics
- [ ] ROI calculations for subscriptions
- [ ] Predictive spending forecasts

**Remaining Technical Requirements:**
- [ ] Advanced data visualization components
- [ ] Machine learning for usage predictions (optional)
- [ ] Trend analysis algorithms

---

### Cancellation Workflows ✂️

**Status:** 🚀 In Progress (Starting Phase 1)
**Priority:** High (User-requested killer feature)
**Estimated Effort:** Large (8 phases)

> Completed sub-items (trial ending reminders, trial period tracking) are recorded in
> docs/_archive/roadmap-phase-1-completed.md.

**Features to Implement:**
- [ ] **Phase 1:** Database schema & migrations (provider_cancellation_info table, subscription status fields)
- [ ] **Phase 2:** AI cancellation research service (OpenAI-powered research for unknown providers)
- [ ] **Phase 3:** Backend API endpoints (cancellation info, status updates, review suggestions)
- [ ] **Phase 4:** Review suggestions algorithm (smart recommendations: trials ending, unused, price increases)
- [ ] **Phase 5:** Frontend cancellation tab (instructions display, difficulty ratings, status tracking)
- [ ] **Phase 6:** Frontend review dashboard (proactive suggestions widget with dismiss/snooze)
- [ ] **Phase 7:** Testing & refinement (unit tests, integration tests, performance optimization)
- [ ] **Phase 8:** Documentation & deployment (API docs, user guides, production deployment)

**Key Innovations:**
- AI-powered cancellation research for any provider (not just pre-built database)
- Smart "subscriptions to review" suggestions (trials ending, unused, price increases)
- Difficulty ratings (easy/medium/hard) with step-by-step instructions
- Pause option support (for services that allow pausing)
- Direct cancellation links when available

**Technical Stack:**
- AI Research: OpenAI GPT-4o-mini with structured JSON output
- Caching: Store research results (90-day refresh cycle)
- Database: PostgreSQL with provider_cancellation_info table
- Frontend: React + Chakra UI with cancellation tab component

**Implementation Plan:**
See detailed plan: `backend/claudedocs/cancellation_workflows_implementation_plan.md`

**Current Phase:** Phase 1 - Database Schema & Migrations

---

### Data Export & Sharing 📤

**Status:** Partially Complete
**Priority:** Medium
**Estimated Effort:** Small

> Completed sub-items (CSV export) are recorded in
> docs/_archive/roadmap-phase-1-completed.md.

**Remaining Features:**
- [ ] Export to Excel with formatting
- [ ] Share costs with roommates/family (split bills)
- [ ] Integration with budgeting apps (YNAB, Mint)
- [ ] Yearly financial reports (PDF)
- [ ] Custom date range exports
- [ ] Scheduled automated exports

**Remaining Technical Requirements:**
- [ ] Excel export with formatting
- [ ] PDF generation for reports
- [ ] Sharing/collaboration system
- [ ] API integrations for third-party apps

---

### UI/UX Improvements 🎨

**Priority:** Medium
**Estimated Effort:** Small-Medium

**Features:**
- [ ] Dark mode support
- [ ] Mobile-responsive improvements
- [ ] Bulk actions (select multiple subscriptions)
- [ ] Drag-and-drop category assignment
- [ ] Advanced search with filters
- [ ] Keyboard shortcuts
- [ ] Customizable dashboard widgets
- [ ] Onboarding tutorial for new users

**Technical Requirements:**
- Theme system (light/dark mode)
- Mobile CSS improvements
- Bulk operation API endpoints
- Drag-and-drop library integration

---

### Testing & Quality ✅

**Priority:** Medium
**Estimated Effort:** Medium-Large

**Features:**
- [ ] Unit tests for AI classifier
- [ ] E2E tests for critical flows
- [ ] Performance optimization
- [ ] Error monitoring (Sentry integration)
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Load testing
- [ ] Security audit

**Technical Requirements:**
- Testing framework setup (pytest, jest)
- E2E testing tools (Playwright)
- Performance monitoring tools
- Error tracking service integration

---

## 💡 Future Ideas

### Payment Method Tracking 💳

**Priority:** Low-Medium
**Estimated Effort:** Medium

**Features:**
- [ ] Track which card/payment method per subscription
- [ ] Alert when payment method expires
- [ ] Payment method switching tracking
- [ ] Failed payment detection
- [ ] Payment method security recommendations

---

### Subscription Recommendations 🤖

**Priority:** Low
**Estimated Effort:** Large

**Features:**
- [ ] AI-powered usage analysis
- [ ] Suggest subscriptions to cancel (low usage)
- [ ] Recommend better deals or alternatives
- [ ] Duplicate subscription detection
- [ ] Family plan upgrade suggestions

---

### Mobile Application 📱

**Priority:** Low
**Estimated Effort:** Very Large

**Features:**
- [ ] Native iOS app
- [ ] Native Android app
- [ ] Push notifications
- [ ] Offline mode
- [ ] Mobile-optimized interface

---

### Advanced Features 🔮

**Priority:** Low
**Estimated Effort:** Various

**Features:**
- [ ] Calendar integration (renewal dates)
- [ ] Subscription marketplace/discovery
- [ ] Social features (compare with friends)
- [ ] Chrome extension for subscription detection
- [ ] Receipt scanning with OCR
- [ ] Multi-currency support improvements
- [ ] Subscription pause/resume automation
- [ ] Contract term tracking
- [ ] Auto-negotiation for better rates

---

## 🏗️ Technical Debt

**Items to address:**
- [ ] Add comprehensive error handling
- [ ] Improve logging and monitoring
- [ ] Database query optimization
- [ ] API rate limiting
- [ ] Security hardening (2FA, rate limiting)
- [ ] Code documentation improvements
- [ ] CI/CD pipeline setup
- [ ] Backup and disaster recovery plan

---

## 📝 Ideas for Discussion

- Should we integrate with bank APIs for automatic transaction matching?
- Consider building a browser extension for automatic subscription detection
- Explore partnership opportunities with subscription services
- Gamification elements (savings goals, achievements)
- Real-time notifications via WebSocket/SSE for better UX

---

*Last Updated: 2026-04-25 (split from ROADMAP.md; see docs/_archive/roadmap-phase-1-completed.md for completed Phase 1 items)*
