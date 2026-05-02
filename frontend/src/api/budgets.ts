import apiClient from './client'
import type { BudgetPeriod } from '../constants/enums'

export interface Budget {
  id: string
  user_id: string
  name: string
  category: string | null
  period: BudgetPeriod
  limit_amount: number
  currency: string
  alert_threshold: number
  alert_enabled: boolean
  created_at: string
  updated_at: string
}

export interface BudgetStatus {
  budget_id: string
  name: string
  category: string | null
  period: string
  limit_amount: number
  current_spending: number
  remaining: number
  percentage_used: number
  status: 'good' | 'warning' | 'exceeded'
  alert_threshold: number
  alert_enabled: boolean
  period_start: string
  period_end: string
  currency: string
}

export interface BudgetAlert {
  budget: BudgetStatus
  alert_type: 'warning' | 'exceeded'
  message: string
}

export interface BudgetCreate {
  name: string
  category?: string | null
  period: BudgetPeriod
  limit_amount: number
  currency?: string
  alert_threshold?: number
  alert_enabled?: boolean
}

export interface BudgetUpdate {
  name?: string
  category?: string | null
  period?: BudgetPeriod
  limit_amount?: number
  currency?: string
  alert_threshold?: number
  alert_enabled?: boolean
}

export const budgetsAPI = {
  /**
   * Get all budgets
   */
  async getAll(): Promise<Budget[]> {
    const response = await apiClient.get('/budgets')
    return response.data
  },

  /**
   * Get all budgets with status information
   */
  async getAllStatus(): Promise<BudgetStatus[]> {
    const response = await apiClient.get('/budgets/status')
    return response.data
  },

  /**
   * Get budget alerts
   */
  async getAlerts(): Promise<BudgetAlert[]> {
    const response = await apiClient.get('/budgets/alerts')
    return response.data
  },

  /**
   * Get a specific budget
   */
  async getById(id: string): Promise<Budget> {
    const response = await apiClient.get(`/budgets/${id}`)
    return response.data
  },

  /**
   * Get budget status by ID
   */
  async getStatusById(id: string): Promise<BudgetStatus> {
    const response = await apiClient.get(`/budgets/${id}/status`)
    return response.data
  },

  /**
   * Create a new budget
   */
  async create(data: BudgetCreate): Promise<Budget> {
    const response = await apiClient.post('/budgets', data)
    return response.data
  },

  /**
   * Update a budget
   */
  async update(id: string, data: BudgetUpdate): Promise<Budget> {
    const response = await apiClient.put(`/budgets/${id}`, data)
    return response.data
  },

  /**
   * Delete a budget
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/budgets/${id}`)
  },
}
