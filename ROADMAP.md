# Subscription Tracker - Feature Roadmap

This document tracks planned features and improvements for the Subscription Tracker application.

## 🎯 Current Status

**Completed Features:**
- ✅ Email sync with JMAP protocol (365-day pagination support)
- ✅ AI-based email classification (OpenAI GPT-4o-mini)
- ✅ Automatic subscription detection and extraction
- ✅ Subscription status auto-update based on email confirmations
- ✅ Manual status refresh functionality
- ✅ Uncertain emails review interface
- ✅ Dashboard with statistics and insights
- ✅ Subscriptions list with filters (category, status)
- ✅ Custom labels for multiple accounts (e.g., different Twitch accounts)
- ✅ Search functionality across subscriptions
- ✅ Budget management API (create, update, track spending)
- ✅ Category management (custom categories with icons/colors)
- ✅ Price change history tracking
- ✅ Data export to CSV
- ✅ Email notifications & alerts system (complete with all 7 types)
  - Trial ending reminders (3 days, 1 day, same day alerts)
  - Renewal reminders (configurable days before renewal)
  - Weekly/monthly spending summary emails
  - Inactive subscription detection alerts
  - Price change notifications with daily monitoring
  - System announcements (admin-initiated broadcasts)
  - Full notification preferences (per-type opt-in/opt-out, in-app + email)
- ✅ Notification center UI (list page with pagination/filters, settings, bell component)
- ✅ Budget Management Frontend (enhanced visualizations & alerts)
  - Budget summary dashboard with 4 stat cards (total limit, spending, remaining, budgets at risk)
  - Spending distribution pie chart
  - Budget usage comparison bar chart
  - Budget alert notifications (daily monitoring with email alerts)

---

## 🚀 In Progress

*Currently no features in progress - ready for next feature implementation!*

---

## 📋 Planned Features

### Admin Panel / Settings Management ⚙️
**Status:** Next up after notifications
**Priority:** High
**Estimated Effort:** Medium

**Features:**
- [ ] API Key Management
  - SendGrid API key configuration
  - OpenAI API key and model version selection
  - JMAP credentials management
- [ ] System Configuration
  - Email notification settings (sender, from address)
  - AI classifier settings (model, temperature, prompt tuning)
  - Default preferences for new users
- [ ] System Health Dashboard
  - API usage statistics (OpenAI tokens, SendGrid emails)
  - Background task monitoring
  - Error logs and debugging
- [ ] User Management (optional)
  - View/manage users
  - Reset passwords
  - View user statistics

**Technical Requirements:**
- Admin-only routes with authentication
- Secure storage for API keys (environment variables or encrypted database)
- Settings model for system configuration
- Health check endpoints
- Admin UI components

---

### Budget Management 💰
**Status:** ✅ Complete
**Priority:** High
**Completed:** 2025-11-19

**Features:**
- ✅ Set monthly/yearly spending limits (API implemented)
- ✅ Track spending against budget (calculation logic ready)
- ✅ Budget categories and allocation (per-category budgets)
- ✅ Compare actual vs. budgeted spending (API endpoints)
- ✅ Budget alerts when approaching limit (integrated with notification system)
- ✅ Visual budget progress indicators (frontend charts - pie & bar)
- ✅ Budget dashboard summary UI (4 stat cards)

**Technical Requirements:**
- ✅ Budget model (user budgets, category budgets)
- ✅ Budget tracking service with statistics
- ✅ Budget API endpoints (CRUD + statistics)
- ✅ Alert system integration (daily Celery task with email notifications)
- ✅ Charts and visualizations (Recharts - pie chart for spending distribution, bar chart for usage comparison)
- ✅ Budget dashboard UI (BudgetSummary and BudgetCharts components)

---

### Subscription Insights & Analytics 📊
**Status:** Partially Complete
**Priority:** High
**Estimated Effort:** Medium

**Features:**
- ✅ Price change history tracking (API + database model)
- ✅ Basic spending statistics (total, by category, by period)
- [ ] Usage recommendations (suggest cancellations based on patterns)
- [ ] Cost comparisons (family plan vs individual)
- [ ] Advanced spending breakdown visualizations
- [ ] Year-over-year cost analysis
- [ ] Subscription lifecycle analytics
- [ ] ROI calculations for subscriptions
- [ ] Predictive spending forecasts

**Technical Requirements:**
- ✅ Historical data tracking (price changes model)
- ✅ Basic analytics engine (statistics API)
- [ ] Advanced data visualization components
- [ ] Machine learning for usage predictions (optional)
- [ ] Trend analysis algorithms

---

### Cancellation Workflows ✂️
**Status:** Partially Complete
**Priority:** Medium
**Estimated Effort:** Medium

**Features:**
- ✅ Reminders to cancel before trial ends (3-day, 1-day, same-day alerts)
- ✅ Trial period tracking (trial_status, trial_end_date fields)
- [ ] Links to cancellation pages for each provider
- [ ] Track cancellation attempts and confirmations
- [ ] "Pause subscription" status
- [ ] Cancellation difficulty ratings
- [ ] Cancellation instructions per provider
- [ ] "Subscriptions to review" suggestions

**Technical Requirements:**
- ✅ Trial period tracking (database model)
- ✅ Trial ending reminders (Celery scheduled tasks)
- [ ] Provider cancellation link database
- [ ] Cancellation status tracking
- [ ] Provider-specific instructions storage

---

### Data Export & Sharing 📤
**Status:** Partially Complete
**Priority:** Medium
**Estimated Effort:** Small

**Features:**
- ✅ Export to CSV (subscriptions data)
- [ ] Export to Excel with formatting
- [ ] Share costs with roommates/family (split bills)
- [ ] Integration with budgeting apps (YNAB, Mint)
- [ ] Yearly financial reports (PDF)
- [ ] Custom date range exports
- [ ] Scheduled automated exports

**Technical Requirements:**
- ✅ CSV export functionality (API endpoint)
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

## 📝 Notes

**Decision Log:**
- 2024-11: Started with email notifications as first priority feature
- Schema bug fix: Changed Pydantic schema from `status` to `is_active` to match database model
- 2025-11-18: Completed trial ending reminder system (backend)
  - Implemented multi-day reminder logic (3 days, 1 day, same day)
  - Created urgency-based email templates with HTML styling
  - Integrated with Celery Beat for daily scheduled checks
  - User preference support for notification opt-in/opt-out
  - SendGrid API key configuration needed for production use
- 2025-11-18: Updated roadmap to reflect actual implementation status
  - Many backend features already complete: budgets, categories, price history, notifications infrastructure
  - Focus shifting to frontend UI for existing backend functionality
  - Trial tracking complete on backend, needs frontend UI integration
- 2025-11-18: Completed full notification system (all 7 types)
  - ✅ Trial ending reminders (3, 1, same day alerts)
  - ✅ Renewal reminders (configurable days before)
  - ✅ Weekly/monthly spending summaries
  - ✅ Inactive subscription detection
  - ✅ Price change monitoring (daily Celery task with 7-day duplicate prevention)
  - ✅ System announcements (admin-initiated broadcasts with user targeting)
  - ✅ Full notification center UI (list page, settings, bell component)
  - Frontend and backend fully integrated with SendGrid email delivery
  - Merged to main (commit 99ebd59)
- 2025-11-19: Completed Budget Management frontend enhancements
  - ✅ Added visual analytics (pie chart for spending distribution, bar chart for usage comparison)
  - ✅ Created summary dashboard with 4 stat cards (total limit, current spending, remaining budget, budgets at risk)
  - ✅ Integrated budget alert notifications with Celery Beat (daily scheduled task)
  - ✅ Budget alerts create in-app notifications and send emails via SendGrid
  - ✅ Database migration for budget alert support (added BUDGET_ALERT notification type)
  - Components: BudgetSummary.tsx, BudgetCharts.tsx, budget_alerts.py task
  - Fully integrated into existing BudgetsPage.tsx with Recharts library

**Ideas for Discussion:**
- Should we integrate with bank APIs for automatic transaction matching?
- Consider building a browser extension for automatic subscription detection
- Explore partnership opportunities with subscription services
- Gamification elements (savings goals, achievements)
- Real-time notifications via WebSocket/SSE for better UX

---

*Last Updated: 2025-11-19* (Budget Management frontend complete with visual analytics and alert notifications)
