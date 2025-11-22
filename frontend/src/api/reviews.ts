import apiClient from './client'
import { ReviewSuggestionsResponse } from '../types'

export const reviewsAPI = {
  /**
   * Get intelligent review suggestions for user's subscriptions
   */
  getSuggestions: async (includeDismissed: boolean = false): Promise<ReviewSuggestionsResponse> => {
    const response = await apiClient.get<ReviewSuggestionsResponse>('/reviews/suggestions', {
      params: { include_dismissed: includeDismissed },
    })
    return response.data
  },
}
