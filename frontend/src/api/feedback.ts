import apiClient from './client'
import {
  FeedbackSubmission,
  QuickFeedback,
  FeedbackResponse,
  DashboardMetrics,
  MyFeedbackResponse,
} from '../types'

export const feedbackAPI = {
  /**
   * Submit detailed feedback on cancellation instructions
   */
  submitFeedback: async (data: FeedbackSubmission): Promise<FeedbackResponse> => {
    const response = await apiClient.post<FeedbackResponse>('/feedback/submit', data)
    return response.data
  },

  /**
   * Submit quick feedback (thumbs up/down)
   */
  submitQuickFeedback: async (data: QuickFeedback): Promise<FeedbackResponse> => {
    const response = await apiClient.post<FeedbackResponse>('/feedback/quick', data)
    return response.data
  },

  /**
   * Get current user's feedback history
   */
  getMyFeedback: async (): Promise<MyFeedbackResponse> => {
    const response = await apiClient.get<MyFeedbackResponse>('/feedback/my-feedback')
    return response.data
  },

  /**
   * Get dashboard metrics (admin only)
   */
  getDashboardMetrics: async (): Promise<DashboardMetrics> => {
    const response = await apiClient.get<DashboardMetrics>('/feedback/metrics/dashboard')
    return response.data
  },
}
