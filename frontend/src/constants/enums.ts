import type { BillingCycle } from '../types'
import type { NotificationType } from '../api/notifications'

export type BudgetPeriod = 'monthly' | 'quarterly' | 'yearly'
export type MailboxSyncFrequency = 'manual' | 'daily' | 'weekly'
export type CurrencyCode = 'USD' | 'EUR' | 'GBP' | 'CAD' | 'JPY' | 'AUD'

export const BILLING_CYCLE_OPTIONS: ReadonlyArray<{
  value: BillingCycle
  label: string
}> = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'one-time', label: 'One-time' },
]

export const BUDGET_PERIOD_OPTIONS: ReadonlyArray<{
  value: BudgetPeriod
  label: string
}> = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'yearly', label: 'Yearly' },
]

export const MAILBOX_SYNC_FREQUENCY_OPTIONS: ReadonlyArray<{
  value: MailboxSyncFrequency
  label: string
}> = [
  { value: 'manual', label: 'Manual only' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
]

export const CURRENCIES: ReadonlyArray<{
  code: CurrencyCode
  name: string
  symbol: string
}> = [
  { code: 'USD', name: 'US Dollar', symbol: '$' },
  { code: 'EUR', name: 'Euro', symbol: '€' },
  { code: 'GBP', name: 'British Pound', symbol: '£' },
  { code: 'JPY', name: 'Japanese Yen', symbol: '¥' },
  { code: 'CAD', name: 'Canadian Dollar', symbol: '$' },
  { code: 'AUD', name: 'Australian Dollar', symbol: '$' },
]

export const NOTIFICATION_TYPE_ICONS: Record<NotificationType, string> = {
  TRIAL_ENDING: '⚠️',
  RENEWAL_REMINDER: '🔔',
  WEEKLY_SUMMARY: '📊',
  MONTHLY_SUMMARY: '📈',
  INACTIVE_SUBSCRIPTION: '⏸️',
  PRICE_CHANGE: '💰',
  BUDGET_ALERT: '💸',
  SYSTEM_ANNOUNCEMENT: '📢',
  SYNC_SKIPPED_MANY: '⏭️',
  SYNC_CIRCUIT_BREAKER: '🛑',
  SYNC_PREVIEW_AVAILABLE: '🔍',
  CANCELLATION_DETECTED: '✂️',
}
