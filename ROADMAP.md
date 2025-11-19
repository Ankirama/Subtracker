# Subscription Tracker - Feature Roadmap

This document tracks planned features and improvements for the Subscription Tracker application.

## 🎯 Current Status

**Completed Features:**
- ✅ Email sync with JMAP protocol (365-day pagination support)
- ✅ AI-based email classification (OpenAI GPT-4o-mini)
- ✅ Automatic subscription detection and extraction
- ✅ Parallel email processing with adaptive batch sizing and retry logic
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
**Status:** ✅ Complete
**Priority:** High
**Completed:** 2025-11-19

**Features:**
- ✅ API Key Management
  - SendGrid API key configuration (database-backed)
  - OpenAI API key configuration (database-backed)
  - Configuration status monitoring (missing/incomplete detection)
- ✅ System Configuration
  - Email notification settings (SendGrid from_email, from_name)
  - AI classifier settings (OpenAI assistant_id, request_delay, max_requests_per_minute)
  - Email processing configuration (batch size, confidence thresholds, sync period)
  - Frontend URL configuration
- ✅ Configuration Health Dashboard
  - Configuration status API endpoint (/admin/config/status)
  - Missing settings detection with recommendations
  - Incomplete settings validation
  - Frontend UI with health indicators and alert banners
- ✅ Admin UI Components
  - Configuration list with pagination and filtering
  - CRUD operations for settings
  - Secret value masking with toggle reveal
  - Health status banners (green success / orange warning / red critical)

**Technical Requirements:**
- ✅ Admin-only routes with authentication (existing admin middleware)
- ✅ Secure storage for API keys (Fernet AES-128 encryption)
- ✅ Settings model (AdminSetting table with JSONB values)
- ✅ Configuration priority system (database > environment variables > defaults)
- ✅ Health check endpoints (GET /admin/config/status)
- ✅ Admin UI components (AdminConfigPage.tsx with Chakra UI)
- ✅ CLI tools (seed_admin_settings.py, check_admin_config.py)

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
- 2025-11-19: Implemented parallel email processing with adaptive batch sizing, caching, and resilience features
  - ✅ Refactored email sync from sequential to parallel batch processing (~10x performance improvement)
  - ✅ Added exponential backoff retry logic for OpenAI API failures (3 retries with 2s, 4s, 8s delays)
  - ✅ Implemented adaptive batch sizing (initial: 10, min: 2) with rate limit detection
  - ✅ Three-stage processing: 1) Parallel classification 2) Parallel extraction 3) Sequential DB operations
  - ✅ Rate limit handling: Automatically reduces batch size on 429 errors, increases when stable
  - ✅ Result caching: Skips extraction for emails already linked to subscriptions (saves API calls)
  - ✅ Smart email content extraction: HTML-to-text conversion, boilerplate removal, key info highlighting
  - ✅ Sync resume capability: Automatically resumes from last position on interruption (1-hour timeout for stale syncs)
  - ✅ Task-level retry: Celery automatic retry with exponential backoff (60s, 120s, 240s) for transient failures
  - ✅ Pagination edge case fix: Position-based tracking prevents unnecessary empty batch fetches when email count is exact multiple of batch size
  - Performance: 100 emails processed in ~10-20 seconds (previously ~200 seconds)
  - API cost reduction: Avoids redundant extraction calls on subsequent syncs
  - Token optimization: 60-70% token reduction via smart content extraction (classification: 1000 chars, extraction: 2500 chars)
  - Resilience: Syncs can resume after network failures, rate limits, or crashes without restarting from beginning
  - Files modified: ai_classifier.py, subscription_extractor.py, email_sync.py, email_cleaner.py (new), mailbox.py, jmap.py
  - Database migration: Added last_sync_started_at, last_sync_position, last_sync_batch_num to mailboxes table
  - Addresses Issues #1 (Sequential Processing), #2 (Fixed Rate Limiting), #3 (No Result Caching), #6 (Context Window Inefficiency), #7 (No Sync Resume), #8 (Missing Task Retry Logic), and #9 (Pagination Edge Case)
- 2025-11-19: Completed Admin Panel Configuration Management System
  - ✅ Database-backed configuration management with 12 settings across 4 categories:
    * Email category: SendGrid API key, from_email, from_name (3 settings)
    * AI category: OpenAI API key, assistant_id, request delays, rate limits (4 settings)
    * Processing category: Batch size, confidence thresholds, sync period (4 settings)
    * Application category: Frontend URL (1 setting)
  - ✅ Configuration priority system: admin_settings database > environment variables > code defaults
  - ✅ Fernet symmetric encryption (AES-128-CBC with HMAC) for API key security
  - ✅ Configuration status monitoring: Missing/incomplete settings detection with actionable recommendations
  - ✅ Configuration helper (config_helper.py): Service layer abstracting configuration source retrieval
  - ✅ Pydantic schema validation fix: Expanded allowed_categories from 5 to 8 values (resolved "failed to load settings" error)
  - ✅ CLI tools for operations:
    * seed_admin_settings.py: Populates database from .env variables with encryption
    * check_admin_config.py: Diagnostic tool with exit codes (0=healthy, 1=issues, 2=error)
  - ✅ API endpoints: Full CRUD + GET /admin/config/status for health monitoring
  - ✅ Frontend AdminConfigPage.tsx: Configuration UI with health banners, missing/incomplete settings alerts, CRUD operations, secret masking
  - ✅ Service integration: Updated auth.py (verification URLs) and email_sync.py (sync period) to use configurable settings
  - ✅ Audit logging: All configuration changes tracked with AdminAuditLog entries
  - Files modified: config_helper.py, admin.py (schemas), auth.py, email_sync.py, admin.ts, AdminConfigPage.tsx
  - Files created: seed_admin_settings.py, check_admin_config.py, admin_config_frontend_fix.md, admin_config_security.md
  - Merged to main (commit 74e59f7)

**Ideas for Discussion:**
- Should we integrate with bank APIs for automatic transaction matching?
- Consider building a browser extension for automatic subscription detection
- Explore partnership opportunities with subscription services
- Gamification elements (savings goals, achievements)
- Real-time notifications via WebSocket/SSE for better UX

---

*Last Updated: 2025-11-19* (Admin Panel Configuration Management: Database-backed settings, Fernet encryption, configuration health monitoring, CLI tools)
