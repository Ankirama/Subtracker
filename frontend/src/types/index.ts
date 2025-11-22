// User types
export interface User {
  id: string
  email: string
  is_admin: boolean
  display_name?: string | null
  created_at: string
  updated_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  display_name?: string  // Optional display name for personalization
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// Email Verification types
export interface EmailVerificationResponse {
  message: string
  email: string
}

export interface EmailVerificationRequest {
  token: string
}

export interface ResendVerificationRequest {
  email: string
}

// Two-Factor Authentication types
export interface TwoFactorRequiredResponse {
  requires_2fa: boolean
  method: 'totp' | 'email'
  message: string
}

export interface TwoFactorSetupRequest {
  method: 'totp' | 'email'
}

export interface TwoFactorSetupResponse {
  method: 'totp' | 'email'
  secret?: string  // TOTP secret (only for TOTP method)
  qr_code?: string  // Base64 QR code data URI (only for TOTP method)
  message: string
}

export interface TwoFactorEnableRequest {
  method: 'totp' | 'email'
  secret?: string  // Required for TOTP
  verification_code: string  // 6-digit code or 8-char backup code
}

export interface TwoFactorEnableResponse {
  success: boolean
  message: string
  backup_codes: string[]  // List of backup codes (only shown once)
}

export interface TwoFactorDisableRequest {
  password: string  // User's password for confirmation
}

export interface TwoFactorVerifyRequest {
  email: string
  code: string  // 6-digit OTP or 8-char backup code (XXXX-XXXX)
  is_backup_code?: boolean
}

export interface TwoFactorStatusResponse {
  enabled: boolean
  method?: 'totp' | 'email'
  backup_codes_remaining: number
}

export interface BackupCodesRegenerateResponse {
  success: boolean
  message: string
  backup_codes: string[]
}

// Account Management types
export interface ProfileUpdateRequest {
  display_name?: string | null
  email?: string | null
}

export interface PasswordChangeRequest {
  current_password: string
  new_password: string
}

export interface UserPreferences {
  theme?: 'light' | 'dark' | 'system'
  language?: string
  currency?: string
  date_format?: string
  timezone?: string
}

export interface UserPreferencesUpdate {
  theme?: 'light' | 'dark' | 'system'
  language?: string
  currency?: string
  date_format?: string
  timezone?: string
}

export interface DeleteAccountRequest {
  password: string
  confirm: boolean
}

export interface MessageResponse {
  message: string
}

export interface PreferencesResponse {
  message: string
  preferences: UserPreferences
}

// Subscription types
export interface Subscription {
  id: string
  user_id: string
  mailbox_id: string | null
  provider: string
  email_sender: string | null
  amount: number | null
  currency: string
  billing_cycle: string
  renewal_date: string | null
  next_renewal_date: string | null  // Computed next future renewal date
  next_billing_date: string | null
  is_active: boolean
  category: string
  tags: string[] | null
  custom_label: string | null
  notes: string | null
  confidence_score: number
  extraction_method: string
  payment_processor: Record<string, any> | null
  first_detected_at: string
  last_confirmed_at: string
  created_at: string
  updated_at: string
  // AI cancellation suggestion fields
  suggested_cancellation_status: string | null
  cancellation_suggestion_reason: string | null
  cancellation_suggestion_created_at: string | null
}

export interface SubscriptionListResponse {
  subscriptions: Subscription[]
  total: number
  page: number
  page_size: number
}

export interface SubscriptionStats {
  total_subscriptions: number
  active_subscriptions: number
  total_monthly_cost: number
  total_yearly_cost: number
  by_category: Record<string, { count: number; total: number }>
  by_billing_cycle: Record<string, number>
  upcoming_renewals: Subscription[]
}

export interface MonthlySpending {
  month: string
  total_cost: number
  subscription_count: number
  new_subscriptions: number
  cancelled_subscriptions: number
}

export interface AnalyticsResponse {
  monthly_spending: MonthlySpending[]
  average_monthly_cost: number
  total_spent: number
  peak_month: string | null
  peak_month_cost: number | null
}

export interface SubscriptionCreate {
  provider: string
  amount?: number | null
  currency?: string
  billing_cycle: string
  renewal_date?: string | null
  category?: string
  custom_label?: string | null
  notes?: string | null
}

export interface SubscriptionUpdate {
  provider?: string
  amount?: number | null
  currency?: string
  billing_cycle?: string
  renewal_date?: string | null
  is_active?: boolean
  category?: string
  custom_label?: string | null
  notes?: string | null
}

// Price History types
export interface PriceHistory {
  id: string
  subscription_id: string
  old_amount: number | null
  new_amount: number
  currency: string
  change_type: 'increase' | 'decrease' | 'initial'
  change_percentage: number | null
  detected_from: string | null
  notes: string | null
  detected_at: string
}

export interface PriceStatistics {
  total_changes: number
  increases: number
  decreases: number
  total_increase_amount: number
  total_decrease_amount: number
  average_change_percentage: number
  latest_price: number | null
  original_price: number | null
}

// Email types
export interface EmailMessage {
  id: string
  mailbox_id: string
  message_id: string
  subject: string
  sender: string
  sender_name: string | null
  recipient: string
  date: string
  body_text: string | null
  body_html: string | null
  is_subscription: boolean
  classification_confidence: number | null
  classification_reasoning: Record<string, any> | null
  created_at: string
}

export interface SubscriptionEmailLink {
  email: EmailMessage
  extraction_role: string | null
  extraction_data: Record<string, any> | null
  created_at: string
}

export interface SubscriptionDetail extends Subscription {
  source_emails: SubscriptionEmailLink[]
}

// Mailbox types
export interface Mailbox {
  id: string
  user_id: string
  provider_type: string
  email_address: string
  display_name: string | null
  is_active: boolean
  last_sync_at: string | null
  last_sync_status: string | null
  last_sync_emails_processed: number | null
  last_sync_subscriptions_found: number | null
  last_sync_error_message: string | null
  sync_frequency: string
  batch_size: number
  import_date_filter: string | null
  created_at: string
  updated_at: string
}

export interface MailboxCreate {
  provider_type: string
  email_address: string
  credentials: {
    server_url: string
    username: string
    password: string
  }
  display_name?: string | null
  sync_frequency?: string
  batch_size?: number
  import_date_filter?: string | null
}

export interface MailboxUpdate {
  display_name?: string | null
  is_active?: boolean
  sync_frequency?: string
  batch_size?: number
  import_date_filter?: string | null
  credentials?: {
    server_url: string
    username: string
    password?: string
  }
}

export interface MailboxSyncStatus {
  mailbox_id: string
  status: string
  last_sync_at: string | null
  total_emails_processed: number | null
  subscriptions_found: number | null
  error_message: string | null
}

export interface MailboxTestResult {
  success: boolean
  message: string
  info: Record<string, any>
}

// AI Sandbox types
export interface EmailTestRequest {
  subject: string
  sender: string
  sender_name?: string | null
  body_text?: string | null
  body_html?: string | null
  date?: string | null
}

export interface ClassificationTestResponse {
  is_subscription: boolean
  confidence: number
  reasoning: string
  category: string
}

export interface ExtractionTestResponse {
  provider: string | null
  amount: number | null
  currency: string | null
  billing_cycle: string | null
  renewal_date: string | null
  custom_label: string | null
  category: string
  confidence_score: number
  extraction_method: string
  raw_response: Record<string, any> | null
}

export interface UncertainEmail {
  id: string
  subject: string
  sender: string
  sender_name: string | null
  date: string
  classification_confidence: number
  is_subscription: boolean
  has_linked_subscription: boolean
  preview: string
}

export interface UncertainEmailsResponse {
  emails: UncertainEmail[]
  total: number
  uncertain_classified: number
  extraction_failed: number
}

export interface EmailDetailResponse {
  id: string
  subject: string
  sender: string
  sender_name: string | null
  recipient: string
  date: string
  body_text: string | null
  body_html: string | null
  is_subscription: boolean
  classification_confidence: number
  classification_reasoning: Record<string, any> | null
  has_linked_subscription: boolean
  linked_subscription_id: string | null
}

export interface ManualSubscriptionCreate {
  email_id: string
  provider: string
  amount?: number | null
  currency?: string | null
  billing_cycle?: string | null
  renewal_date?: string | null
  custom_label?: string | null
  category?: string
  notes?: string | null
}

export interface BulkMarkNotSubscriptionRequest {
  email_ids: string[]
}

export interface BulkMarkNotSubscriptionResponse {
  success: boolean
  processed: number
  failed: number
  errors: string[]
}

// Cancellation types
export type CancellationStatus = 'active' | 'pending_cancellation' | 'paused' | 'cancelled'
export type DifficultyRating = 'easy' | 'medium' | 'hard'
export type ReviewSuggestionReason =
  | 'trial_ending'
  | 'trial_ending_soon'
  | 'likely_unused'
  | 'price_increased'
  | 'expensive_unused'
  | 'duplicate_detected'

export interface ProviderCancellationInfo {
  id: string
  provider_name: string
  cancellation_url: string | null
  difficulty_rating: DifficultyRating
  instructions: string[] | null
  instructions_source: string
  requires_phone_call: boolean
  requires_chat: boolean
  allows_pause: boolean
  pause_instructions: string[] | null
  additional_notes: string | null
  estimated_time_minutes: number | null
  cancellation_gotchas: string[] | null
  ai_confidence_score: number | null
  created_at: string
  updated_at: string
  is_verified: boolean
  needs_reverification: boolean
  is_ai_generated: boolean
}

export interface AIResearchRequest {
  provider_name: string
  force_refresh?: boolean
}

export interface AIResearchResponse {
  provider_name: string
  cancellation_url: string | null
  difficulty_rating: DifficultyRating
  instructions: string[]
  requires_phone_call: boolean
  requires_chat: boolean
  allows_pause: boolean
  pause_instructions: string[] | null
  additional_notes: string | null
  estimated_time_minutes: number | null
  cancellation_gotchas: string[] | null
  ai_confidence_score: number
  sources_consulted: string[] | null
  research_timestamp: string
}

export interface SubscriptionCancellationInfo {
  subscription_id: string
  provider: string
  cancellation_status: CancellationStatus
  cancellation_requested_at: string | null
  cancellation_confirmed_at: string | null
  cancellation_notes: string | null
  provider_info: ProviderCancellationInfo | null
}

export interface CancellationStatusUpdate {
  cancellation_status: CancellationStatus
  cancellation_notes?: string | null
}

export interface ReviewSuggestion {
  subscription_id: string
  provider: string
  amount: number | null
  currency: string
  billing_cycle: string
  reason: ReviewSuggestionReason
  priority: 'critical' | 'high' | 'medium' | 'low'
  message: string
  action_by_date: string | null
  days_since_last_email: number | null
  price_change_amount: number | null
  price_change_date: string | null
  dismissed_at: string | null
  snoozed_until: string | null
}

export interface ReviewSuggestionsResponse {
  suggestions: ReviewSuggestion[]
  total_count: number
  critical_count: number
  high_priority_count: number
}

// Feedback types
export type FeedbackTypeEnum = 'helpful' | 'not_helpful' | 'inaccurate' | 'incomplete' | 'worked' | 'failed'

export interface FeedbackSubmission {
  provider_cancellation_id: string
  feedback_type: FeedbackTypeEnum
  successfully_cancelled?: boolean | null
  time_taken_minutes?: number | null
  helpfulness_rating?: number | null  // 1-5
  accuracy_rating?: number | null  // 1-5
  comment?: string | null
  issues_encountered?: string[] | null
  device_type?: string | null
}

export interface QuickFeedback {
  provider_cancellation_id: string
  feedback_type: 'helpful' | 'not_helpful'
}

export interface FeedbackResponse {
  id: string
  user_id: string
  provider_cancellation_id: string
  provider_name: string
  feedback_type: FeedbackTypeEnum
  successfully_cancelled: boolean | null
  time_taken_minutes: number | null
  helpfulness_rating: number | null
  accuracy_rating: number | null
  comment: string | null
  issues_encountered: any[] | null
  ai_confidence_at_feedback: number | null
  validation_quality_at_feedback: number | null
  prompt_version_at_feedback: string | null
  device_type: string | null
  created_at: string
  updated_at: string
}

export interface ProviderMetrics {
  provider_name: string
  total_feedback: number
  helpful_count: number
  not_helpful_count: number
  success_rate: number | null
  avg_time_minutes: number | null
  avg_helpfulness: number | null
  avg_accuracy: number | null
  common_issues: string[]
}

export interface ValidationMetrics {
  total_feedback: number
  high_confidence_success_rate: number | null
  low_confidence_success_rate: number | null
  accuracy_improvement_over_time: Record<string, any> | null
  providers_needing_update: string[]
}

export interface DashboardMetrics {
  overall_metrics: ValidationMetrics
  provider_metrics: ProviderMetrics[]
}

export interface MyFeedbackResponse {
  feedback: FeedbackResponse[]
  total: number
}

// API Error types
export interface APIError {
  detail: string
}
