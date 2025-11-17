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

---

## 🚀 In Progress

### Email Notifications & Alerts 🔔
**Status:** In Progress
**Priority:** High
**Description:** Alert users about important subscription events

**Features:**
- [ ] Alert X days before renewal (configurable per subscription)
- [ ] Weekly/monthly spending summary emails
- [ ] Notifications when inactive subscriptions are detected
- [ ] Alerts on unusual charges or price changes
- [ ] Email preferences management (frequency, types of alerts)

**Technical Requirements:**
- Email service integration (SendGrid, AWS SES, or similar)
- Notification scheduling system (Celery periodic tasks)
- User notification preferences table
- Email templates (HTML + plain text)

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
**Priority:** High
**Estimated Effort:** Medium

**Features:**
- [ ] Set monthly/yearly spending limits
- [ ] Budget alerts when approaching limit
- [ ] Track spending trends over time
- [ ] Compare actual vs. budgeted spending
- [ ] Budget categories and allocation
- [ ] Visual budget progress indicators

**Technical Requirements:**
- Budget model (user budgets, category budgets)
- Budget tracking service
- Alert system integration
- Charts and visualizations

---

### Subscription Insights & Analytics 📊
**Priority:** High
**Estimated Effort:** Medium-Large

**Features:**
- [ ] Price change history tracking
- [ ] Usage recommendations (suggest cancellations)
- [ ] Cost comparisons (family plan vs individual)
- [ ] Spending breakdown by category over time
- [ ] Year-over-year cost analysis
- [ ] Subscription lifecycle analytics
- [ ] ROI calculations for subscriptions

**Technical Requirements:**
- Historical data tracking (price changes)
- Analytics engine
- Data visualization components
- Machine learning for usage predictions (optional)

---

### Cancellation Workflows ✂️
**Priority:** Medium
**Estimated Effort:** Medium

**Features:**
- [ ] Links to cancellation pages for each provider
- [ ] Reminders to cancel before trial ends
- [ ] Track cancellation attempts and confirmations
- [ ] "Pause subscription" status
- [ ] Cancellation difficulty ratings
- [ ] Cancellation instructions per provider
- [ ] "Subscriptions to review" suggestions

**Technical Requirements:**
- Provider cancellation link database
- Trial period tracking
- Cancellation status tracking
- Provider-specific instructions storage

---

### Data Export & Sharing 📤
**Priority:** Medium
**Estimated Effort:** Small-Medium

**Features:**
- [ ] Export to CSV/Excel for tax purposes
- [ ] Share costs with roommates/family (split bills)
- [ ] Integration with budgeting apps (YNAB, Mint)
- [ ] Yearly financial reports (PDF)
- [ ] Custom date range exports
- [ ] Scheduled automated exports

**Technical Requirements:**
- CSV/Excel export functionality
- PDF generation for reports
- Sharing/collaboration system
- API integrations for third-party apps

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

**Ideas for Discussion:**
- Should we integrate with bank APIs for automatic transaction matching?
- Consider building a browser extension for automatic subscription detection
- Explore partnership opportunities with subscription services
- Gamification elements (savings goals, achievements)

---

*Last Updated: 2024-11-16*
