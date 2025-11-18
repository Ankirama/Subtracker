import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ChakraProvider } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import { ProtectedRoute } from './components/common/ProtectedRoute'
import { AdminRoute } from './components/common/AdminRoute'
import { DashboardLayout } from './components/common/DashboardLayout'
import { AdminLayout } from './components/admin/AdminLayout'
import { LoginPage } from './components/auth/LoginPage'
import { RegisterPage } from './components/auth/RegisterPage'
import { DashboardPage } from './components/subscriptions/DashboardPage'
import { SubscriptionsPage } from './components/subscriptions/SubscriptionsPage'
import { SubscriptionDetailPage } from './components/subscriptions/SubscriptionDetailPage'
import { MailboxesPage } from './components/mailboxes/MailboxesPage'
import { AnalyticsPage } from './components/analytics/AnalyticsPage'
import { AISandboxPage } from './components/ai-sandbox/AISandboxPage'
import { NotificationSettingsPage } from './components/notifications/NotificationSettingsPage'
import { NotificationListPage } from './components/notifications/NotificationListPage'
import { OptimizePage } from './components/optimize/OptimizePage'
import { BudgetsPage } from './components/budgets/BudgetsPage'
import { CategoriesPage } from './components/categories'
import { ConfigPage } from './pages/admin/ConfigPage'

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
    <ChakraProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Protected routes */}
              <Route element={<ProtectedRoute />}>
                <Route element={<DashboardLayout />}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/subscriptions" element={<SubscriptionsPage />} />
                  <Route path="/subscriptions/:id" element={<SubscriptionDetailPage />} />
                  <Route path="/categories" element={<CategoriesPage />} />
                  <Route path="/mailboxes" element={<MailboxesPage />} />
                  <Route path="/budgets" element={<BudgetsPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />
                  <Route path="/optimize" element={<OptimizePage />} />
                  <Route path="/ai-sandbox" element={<AISandboxPage />} />
                  <Route path="/notifications" element={<NotificationListPage />} />
                  <Route path="/notifications/settings" element={<NotificationSettingsPage />} />
                </Route>
              </Route>

              {/* Admin routes */}
              <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
                <Route path="config" element={<ConfigPage />} />
                <Route path="users" element={<div>Users Page (Coming Soon)</div>} />
                <Route path="logs" element={<div>Logs Page (Coming Soon)</div>} />
                <Route path="security" element={<div>Security Events Page (Coming Soon)</div>} />
              </Route>

              {/* Default redirect */}
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ChakraProvider>
  )
}

export default App
