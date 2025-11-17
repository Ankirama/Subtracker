import { apiClient } from './client'

export interface Recommendation {
  type: string
  category: string
  title: string
  description: string
  potential_savings: number
  action: string
  affected_subscriptions: string[]
  priority: 'high' | 'medium' | 'low'
}

export interface OptimizationAnalysis {
  total_recommendations: number
  potential_savings: number
  recommendations: Recommendation[]
  insights: string[]
  analyzed_at?: string
}

export const optimizeApi = {
  async getRecommendations(): Promise<OptimizationAnalysis> {
    const response = await apiClient.get('/optimize/recommendations')
    return response.data
  },
}
