import apiClient from './client'
import {
  AIResearchRequest,
  AIResearchResponse,
  ProviderCancellationInfo,
  SubscriptionCancellationInfo,
  CancellationStatusUpdate,
} from '../types'

export const cancellationAPI = {
  /**
   * Research cancellation instructions for a provider using AI
   */
  researchProvider: async (data: AIResearchRequest): Promise<AIResearchResponse> => {
    const response = await apiClient.post<AIResearchResponse>('/cancellation/research', data)
    return response.data
  },

  /**
   * Get cached cancellation information for a provider
   */
  getProviderInfo: async (providerName: string): Promise<ProviderCancellationInfo> => {
    const response = await apiClient.get<ProviderCancellationInfo>(
      `/cancellation/providers/${encodeURIComponent(providerName)}`
    )
    return response.data
  },

  /**
   * Get cancellation information for a specific subscription
   */
  getSubscriptionCancellationInfo: async (
    subscriptionId: string
  ): Promise<SubscriptionCancellationInfo> => {
    const response = await apiClient.get<SubscriptionCancellationInfo>(
      `/cancellation/subscriptions/${subscriptionId}`
    )
    return response.data
  },

  /**
   * Update subscription cancellation status
   */
  updateCancellationStatus: async (
    subscriptionId: string,
    data: CancellationStatusUpdate
  ): Promise<SubscriptionCancellationInfo> => {
    const response = await apiClient.patch<SubscriptionCancellationInfo>(
      `/cancellation/subscriptions/${subscriptionId}/status`,
      data
    )
    return response.data
  },
}
