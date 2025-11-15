import apiClient from './client'
import {
  Subscription,
  SubscriptionDetail,
  SubscriptionListResponse,
  SubscriptionStats,
  SubscriptionCreate,
  SubscriptionUpdate,
} from '../types'

export const subscriptionsAPI = {
  getAll: async (params?: {
    page?: number
    page_size?: number
    category?: string
    is_active?: boolean
    search?: string
    sort_by?: string
  }): Promise<SubscriptionListResponse> => {
    const response = await apiClient.get<SubscriptionListResponse>('/subscriptions', { params })
    return response.data
  },

  getById: async (id: string): Promise<SubscriptionDetail> => {
    const response = await apiClient.get<SubscriptionDetail>(`/subscriptions/${id}`)
    return response.data
  },

  getStats: async (): Promise<SubscriptionStats> => {
    const response = await apiClient.get<SubscriptionStats>('/subscriptions/stats')
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
}
