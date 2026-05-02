import apiClient from './client'

export type ConfidenceBucket = 'auto_saved' | 'pending_review'
export type UpdateType = 'price_change' | 'cancellation_detected'

export interface NewSubscriptionPreview {
  id: string
  provider: string
  custom_label: string | null
  amount: number | null
  currency: string
  billing_cycle: string
  category: string | null
  confidence_bucket: ConfidenceBucket
  source_email_subject: string | null
  source_email_date: string | null
}

export interface UpdatedSubscriptionPreview {
  id: string
  provider: string
  update_type: UpdateType
  before: Record<string, unknown>
  after: Record<string, unknown>
  source_email_subject: string | null
  source_email_date: string | null
}

export interface SyncPreviewMeta {
  id: string
  mailbox_id: string
  mailbox_email: string
  started_at: string
  completed_at: string | null
  new_emails_count: number | null
}

export interface SyncPreviewResponse {
  sync_history: SyncPreviewMeta
  new_subscriptions: NewSubscriptionPreview[]
  updated_subscriptions: UpdatedSubscriptionPreview[]
}

export const syncPreviewAPI = {
  get: async (syncHistoryId: string): Promise<SyncPreviewResponse> => {
    const response = await apiClient.get<SyncPreviewResponse>(
      `/sync-history/${syncHistoryId}/preview`,
    )
    return response.data
  },
}
