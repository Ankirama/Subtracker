import apiClient from './client'
import {
  Subscription,
  SubscriptionDetail,
  SubscriptionListResponse,
  SubscriptionStats,
  SubscriptionCreate,
  SubscriptionUpdate,
  PriceHistory,
  PriceStatistics,
  AnalyticsResponse,
} from '../types'

export const subscriptionsAPI = {
  getAll: async (params?: {
    page?: number
    page_size?: number
    category?: string
    status?: string
    search?: string
    sort_by?: string
    exclude_trials?: boolean
  }): Promise<SubscriptionListResponse> => {
    const response = await apiClient.get<SubscriptionListResponse>('/subscriptions', { params })
    return response.data
  },

  getById: async (id: string): Promise<SubscriptionDetail> => {
    const response = await apiClient.get<SubscriptionDetail>(`/subscriptions/${id}`)
    return response.data
  },

  getStats: async (params?: { exclude_trials?: boolean }): Promise<SubscriptionStats> => {
    const response = await apiClient.get<SubscriptionStats>('/subscriptions/stats', { params })
    return response.data
  },

  getAnalytics: async (months: number = 12): Promise<AnalyticsResponse> => {
    const response = await apiClient.get<AnalyticsResponse>('/subscriptions/analytics/trends', {
      params: { months }
    })
    return response.data
  },

  create: async (data: SubscriptionCreate): Promise<Subscription> => {
    const response = await apiClient.post<Subscription>('/subscriptions', data)
    return response.data
  },

  update: async (id: string, data: SubscriptionUpdate): Promise<Subscription> => {
    const response = await apiClient.put<Subscription>(`/subscriptions/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/subscriptions/${id}`)
  },

  updateStatus: async (mailboxId?: string): Promise<{
    success: boolean
    total_activated: number
    total_deactivated: number
    mailboxes_updated: number
    message: string
  }> => {
    const params = mailboxId ? { mailbox_id: mailboxId } : {}
    const response = await apiClient.post('/subscriptions/update-status', {}, { params })
    return response.data
  },

  submitFeedback: async (data: {
    subscription_id: string
    feedback_type: 'not_subscription' | 'duplicate' | 'wrong_amount' | 'wrong_provider' | 'wrong_category' | 'wrong_billing_cycle' | 'other'
    feedback_text?: string
  }): Promise<void> => {
    await apiClient.post('/subscriptions/feedback', data)
  },

  getPriceHistory: async (subscriptionId: string): Promise<PriceHistory[]> => {
    const response = await apiClient.get<PriceHistory[]>(`/subscriptions/${subscriptionId}/price-history`)
    return response.data
  },

  getPriceStatistics: async (subscriptionId: string): Promise<PriceStatistics> => {
    const response = await apiClient.get<PriceStatistics>(`/subscriptions/${subscriptionId}/price-statistics`)
    return response.data
  },

  getDuplicates: async (): Promise<any[]> => {
    const response = await apiClient.get('/subscriptions/duplicates')
    return response.data
  },

  merge: async (sourceId: string, targetId: string): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post(`/subscriptions/${sourceId}/merge/${targetId}`)
    return response.data
  },

  mergeGroup: async (
    targetId: string,
    sourceIds: string[]
  ): Promise<{
    success: boolean
    message: string
    target_subscription_id: string
    deleted_subscription_ids: string[]
  }> => {
    const response = await apiClient.post('/subscriptions/merge-group', {
      target_id: targetId,
      source_ids: sourceIds,
    })
    return response.data
  },

  split: async (
    id: string,
    emailGroups: Array<{
      email_ids: string[]
      custom_label?: string
      amount?: number
      service_references?: Record<string, any>
    }>
  ): Promise<{ success: boolean; message: string; subscriptions: Subscription[] }> => {
    const response = await apiClient.post(`/subscriptions/${id}/split`, emailGroups)
    return response.data
  },

  acceptCancellationSuggestion: async (id: string): Promise<Subscription> => {
    const response = await apiClient.post<Subscription>(`/subscriptions/${id}/accept-suggestion`)
    return response.data
  },

  dismissCancellationSuggestion: async (id: string): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post<{ success: boolean; message: string }>(`/subscriptions/${id}/dismiss-suggestion`)
    return response.data
  },
}
