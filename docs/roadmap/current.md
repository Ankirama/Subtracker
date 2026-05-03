# Roadmap — Active

> See docs/_archive/roadmap-phase-1-completed.md for historical/completed items.
> See docs/roadmap/mobile.md for the mobile responsive roadmap.

This document tracks planned and in-progress features for the Subscription Tracker application.

---

## 🚀 In Progress

*Currently no features in progress - ready for next feature implementation!*

---

## 📋 Planned Features

### Post-sync Subscription Preview 🔍

**Priority:** Medium
**Estimated Effort:** Small-Medium

When a sync completes and creates new subscriptions, surface them in a modal/panel so the user can immediately review what was just discovered, edit or reject obvious mistakes, and avoid having to scroll through the full list to find them.

**Features:**
- [ ] Post-sync modal listing subscriptions created during the run (grouped: high-confidence auto-saved vs. pending-review)
- [ ] Inline edit (label, amount, billing cycle, category) without leaving the modal
- [ ] One-click reject / keep / "send to review" actions
- [ ] Linkable summary entry in the notification feed (so the user can re-open the preview later if they dismiss the modal)
- [ ] Optionally include subscriptions whose existing record was confirmed/refreshed by the sync (price changes, cancellation detected)

**Technical Requirements:**
- Backend: tag subscriptions/email_processing_records with the `sync_history_id` that produced/touched them (already present on most rows — verify), expose `GET /api/sync-history/{id}/discoveries`
- Frontend: modal component, hook into the existing sync-completion notification, persist "seen" state per sync_history_id so the modal doesn't reopen
- i18n: en + fr strings

---

### Fastmail OAuth Integration 📨

**Priority:** Medium
**Estimated Effort:** Medium

Currently Fastmail users must generate an API/app-password manually and paste it into the JMAP form. Fastmail supports OAuth 2.0 with PKCE — wiring this up would mirror the Gmail/Outlook flow and remove the friction (and the support load when users pick the wrong app-password type, as we just hit).

**Features:**
- [ ] Fastmail OAuth provider in `app/email_providers/` (auth code + refresh flow, JMAP capability negotiation post-auth)
- [ ] OAuth callback endpoint and credential persistence (mirror Gmail pattern)
- [ ] "Connect Fastmail" button in `AddMailboxModal` (alongside Gmail), keep manual JMAP form available as a fallback for non-Fastmail JMAP servers
- [ ] Refresh token handling + `needs_reconnect` flag wiring (reuse existing OAuth-failure plumbing)

**Technical Requirements:**
- Fastmail OAuth client registration (client_id / client_secret, redirect URI in env)
- Scopes needed: `urn:ietf:params:jmap:mail` at minimum
- Reuse existing OAuth state/PKCE infra used for Gmail
- Migration: none — existing JMAP rows keep working

---

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

## 🐛 Known Bugs

*No known bugs at the moment.*

---

## 📝 Ideas for Discussion

- Should we integrate with bank APIs for automatic transaction matching?
- Consider building a browser extension for automatic subscription detection
- Explore partnership opportunities with subscription services
- Gamification elements (savings goals, achievements)
- Real-time notifications via WebSocket/SSE for better UX

---

*Last Updated: 2026-05-03 (Cancellation Workflows: visibility polish fully shipped; section moved to archive)*
