import apiClient from './client'
import {
  EmailTestRequest,
  ClassificationTestResponse,
  ExtractionTestResponse,
  UncertainEmailsResponse,
  EmailDetailResponse,
  ManualSubscriptionCreate,
  BulkMarkNotSubscriptionRequest,
  BulkMarkNotSubscriptionResponse,
} from '../types'

export const aiSandboxAPI = {
  testClassification: async (data: EmailTestRequest): Promise<ClassificationTestResponse> => {
    const response = await apiClient.post<ClassificationTestResponse>('/ai-sandbox/test-classification', data)
    return response.data
  },

  testExtraction: async (data: EmailTestRequest): Promise<ExtractionTestResponse> => {
    const response = await apiClient.post<ExtractionTestResponse>('/ai-sandbox/test-extraction', data)
    return response.data
  },

  getUncertainEmails: async (limit?: number): Promise<UncertainEmailsResponse> => {
    const response = await apiClient.get<UncertainEmailsResponse>('/ai-sandbox/uncertain-emails', {
      params: { limit },
    })
    return response.data
  },

  getEmailDetail: async (emailId: string): Promise<EmailDetailResponse> => {
    const response = await apiClient.get<EmailDetailResponse>(`/ai-sandbox/email/${emailId}`)
    return response.data
  },

  createSubscription: async (data: ManualSubscriptionCreate): Promise<{ success: boolean; subscription_id: string; message: string }> => {
    const response = await apiClient.post('/ai-sandbox/create-subscription', data)
    return response.data
  },

  markNotSubscription: async (emailId: string): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post(`/ai-sandbox/mark-not-subscription/${emailId}`)
    return response.data
  },

  bulkMarkNotSubscription: async (data: BulkMarkNotSubscriptionRequest): Promise<BulkMarkNotSubscriptionResponse> => {
    const response = await apiClient.post<BulkMarkNotSubscriptionResponse>('/ai-sandbox/bulk-mark-not-subscription', data)
    return response.data
  },
}
