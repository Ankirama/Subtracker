import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ChakraProvider, Spinner, Center } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import theme from './theme'
import { AuthProvider } from './contexts/AuthContext'
import { ProtectedRoute } from './components/common/ProtectedRoute'
import { AdminRoute } from './components/common/AdminRoute'
import { DashboardLayout } from './components/common/DashboardLayout'
import { AdminLayout } from './components/admin/AdminLayout'

// Lazy loaded auth pages
const LoginPage = lazy(() => import('./components/auth/LoginPage').then(m => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./components/auth/RegisterPage').then(m => ({ default: m.RegisterPage })))
const VerifyEmailPage = lazy(() => import('./components/auth/VerifyEmailPage').then(m => ({ default: m.VerifyEmailPage })))
const ResendVerificationPage = lazy(() => import('./components/auth/ResendVerificationPage').then(m => ({ default: m.ResendVerificationPage })))

// Lazy loaded subscription pages
const DashboardPage = lazy(() => import('./components/subscriptions/DashboardPage').then(m => ({ default: m.DashboardPage })))
const SubscriptionsPage = lazy(() => import('./components/subscriptions/SubscriptionsPage').then(m => ({ default: m.SubscriptionsPage })))
const SubscriptionDetailPage = lazy(() => import('./components/subscriptions/SubscriptionDetailPage').then(m => ({ default: m.SubscriptionDetailPage })))
const ReviewDashboardPage = lazy(() => import('./components/subscriptions/ReviewDashboardPage').then(m => ({ default: m.ReviewDashboardPage })))
const DuplicatesPage = lazy(() => import('./components/subscriptions/DuplicatesPage'))

// Lazy loaded feature pages
const MailboxesPage = lazy(() => import('./components/mailboxes/MailboxesPage').then(m => ({ default: m.MailboxesPage })))
const SyncErrorsPage = lazy(() => import('./components/mailboxes/SyncErrorsPage').then(m => ({ default: m.SyncErrorsPage })))
const AnalyticsPage = lazy(() => import('./components/analytics/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const AISandboxPage = lazy(() => import('./components/ai-sandbox/AISandboxPage').then(m => ({ default: m.AISandboxPage })))
const NotificationSettingsPage = lazy(() => import('./components/notifications/NotificationSettingsPage').then(m => ({ default: m.NotificationSettingsPage })))
const NotificationListPage = lazy(() => import('./components/notifications/NotificationListPage').then(m => ({ default: m.NotificationListPage })))
const OptimizePage = lazy(() => import('./components/optimize/OptimizePage').then(m => ({ default: m.OptimizePage })))
const BudgetsPage = lazy(() => import('./components/budgets/BudgetsPage').then(m => ({ default: m.BudgetsPage })))
const CategoriesPage = lazy(() => import('./components/categories').then(m => ({ default: m.CategoriesPage })))
const TwoFactorSettingsPage = lazy(() => import('./components/settings/TwoFactorSettingsPage').then(m => ({ default: m.TwoFactorSettingsPage })))
const SettingsPage = lazy(() => import('./components/settings/SettingsPage').then(m => ({ default: m.SettingsPage })))

// Lazy loaded admin pages
const ConfigPage = lazy(() => import('./pages/admin/ConfigPage').then(m => ({ default: m.ConfigPage })))
const AdminAnnouncementsPage = lazy(() => import('./components/admin/AdminAnnouncementsPage').then(m => ({ default: m.AdminAnnouncementsPage })))
const AdminUsersPage = lazy(() => import('./components/admin/AdminUsersPage').then(m => ({ default: m.AdminUsersPage })))

// Landing page
const LandingPageWrapper = lazy(() => import('./components/landing').then(m => ({ default: m.LandingPageWrapper })))
const AdminLogsPage = lazy(() => import('./components/admin/AdminLogsPage').then(m => ({ default: m.AdminLogsPage })))
const AdminSecurityEventsPage = lazy(() => import('./components/admin/AdminSecurityEventsPage').then(m => ({ default: m.AdminSecurityEventsPage })))
const AdminIPWhitelistPage = lazy(() => import('./components/admin/AdminIPWhitelistPage').then(m => ({ default: m.AdminIPWhitelistPage })))
const AdminFeedbackMetricsPage = lazy(() => import('./components/admin/AdminFeedbackMetricsPage').then(m => ({ default: m.AdminFeedbackMetricsPage })))
const AdminInvitesPage = lazy(() => import('./components/admin/AdminInvitesPage').then(m => ({ default: m.AdminInvitesPage })))
const AdminSyncErrorsPage = lazy(() => import('./components/admin/AdminSyncErrorsPage').then(m => ({ default: m.AdminSyncErrorsPage })))

// Loading fallback component
const LoadingFallback = () => (
  <Center h="100vh">
    <Spinner size="xl" color="blue.500" thickness="4px" />
  </Center>
)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  return (
    <ChakraProvider theme={theme}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <Suspense fallback={<LoadingFallback />}>
              <Routes>
                {/* Public routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/verify-email/:token" element={<VerifyEmailPage />} />
                <Route path="/resend-verification" element={<ResendVerificationPage />} />

                {/* Protected routes */}
                <Route element={<ProtectedRoute />}>
                  <Route element={<DashboardLayout />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/subscriptions" element={<SubscriptionsPage />} />
                    <Route path="/subscriptions/:id" element={<SubscriptionDetailPage />} />
                    <Route path="/duplicates" element={<DuplicatesPage />} />
                    <Route path="/reviews" element={<ReviewDashboardPage />} />
                    <Route path="/categories" element={<CategoriesPage />} />
                    <Route path="/mailboxes" element={<MailboxesPage />} />
                    <Route path="/mailboxes/:mailboxId/sync-errors" element={<SyncErrorsPage />} />
                    <Route path="/budgets" element={<BudgetsPage />} />
                    <Route path="/analytics" element={<AnalyticsPage />} />
                    <Route path="/optimize" element={<OptimizePage />} />
                    <Route path="/ai-sandbox" element={<AISandboxPage />} />
                    <Route path="/notifications" element={<NotificationListPage />} />
                    <Route path="/notifications/settings" element={<NotificationSettingsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/settings/2fa" element={<TwoFactorSettingsPage />} />
                  </Route>
                </Route>

                {/* Admin routes */}
                <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
                  <Route path="config" element={<ConfigPage />} />
                  <Route path="announcements" element={<AdminAnnouncementsPage />} />
                  <Route path="users" element={<AdminUsersPage />} />
                  <Route path="logs" element={<AdminLogsPage />} />
                  <Route path="security" element={<AdminSecurityEventsPage />} />
                  <Route path="ip-whitelist" element={<AdminIPWhitelistPage />} />
                  <Route path="feedback-metrics" element={<AdminFeedbackMetricsPage />} />
                  <Route path="invites" element={<AdminInvitesPage />} />
                  <Route path="sync-errors" element={<AdminSyncErrorsPage />} />
                </Route>

                {/* Landing page for unauthenticated users, dashboard for authenticated */}
                <Route path="/" element={<LandingPageWrapper />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Suspense>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ChakraProvider>
  )
}

export default App
