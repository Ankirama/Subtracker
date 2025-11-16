// User types
export interface User {
  id: string
  email: string
  is_admin: boolean
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
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
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

// API Error types
export interface APIError {
  detail: string
}
