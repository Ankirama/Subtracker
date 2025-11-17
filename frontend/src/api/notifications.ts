import apiClient from './client'

export interface Notification {
  id: string
  user_id: string
  type: 'renewal_reminder' | 'weekly_summary' | 'monthly_summary' | 'inactive_subscription' | 'price_change' | 'system_announcement'
  priority: 'low' | 'medium' | 'high'
  title: string
  message: string
  related_subscription_id?: string
  notification_metadata?: Record<string, any>
  is_read: boolean
  read_at?: string
  email_sent: boolean
  email_sent_at?: string
  created_at: string
  expires_at?: string
}

export interface NotificationListResponse {
  notifications: Notification[]
  total: number
  unread_count: number
  page: number
  page_size: number
  has_more: boolean
}

export interface NotificationPreference {
  id: string
  user_id: string
  notification_type: string
  enabled: boolean
  in_app_enabled: boolean
  email_enabled: boolean
  days_before_renewal?: number
  summary_day_of_week?: number
  summary_day_of_month?: number
  created_at: string
  updated_at: string
}

export interface NotificationPreferencesListResponse {
  preferences: NotificationPreference[]
}

export const notificationsApi = {
  /**
   * Get list of notifications with pagination and filtering
   */
  async getNotifications(params?: {
    page?: number
    page_size?: number
    unread_only?: boolean
    notification_type?: string
  }): Promise<NotificationListResponse> {
    const response = await apiClient.get('/notifications', { params })
    return response.data
  },

  /**
   * Get unread notification count
   */
  async getUnreadCount(): Promise<{ unread_count: number }> {
    const response = await apiClient.get('/notifications/unread-count')
    return response.data
  },

  /**
   * Mark specific notifications as read
   */
  async markAsRead(notificationIds: string[]): Promise<{ success: boolean; marked_read: number }> {
    const response = await apiClient.post('/notifications/mark-read', {
      notification_ids: notificationIds,
    })
    return response.data
  },

  /**
   * Mark all notifications as read
   */
  async markAllAsRead(): Promise<{ success: boolean; marked_read: number }> {
    const response = await apiClient.post('/notifications/mark-all-read', {})
    return response.data
  },

  /**
   * Delete a notification
   */
  async deleteNotification(notificationId: string): Promise<{ success: boolean }> {
    const response = await apiClient.delete(`/notifications/${notificationId}`)
    return response.data
  },

  /**
   * Get user's notification preferences
   */
  async getPreferences(): Promise<NotificationPreferencesListResponse> {
    const response = await apiClient.get('/notifications/preferences')
    return response.data
  },

  /**
   * Update a notification preference
   */
  async updatePreference(
    notificationType: string,
    updates: {
      enabled?: boolean
      in_app_enabled?: boolean
      email_enabled?: boolean
      days_before_renewal?: number
      summary_day_of_week?: number
      summary_day_of_month?: number
    }
  ): Promise<NotificationPreference> {
    const response = await apiClient.put(`/notifications/preferences/${notificationType}`, updates)
    return response.data
  },

  /**
   * Get upcoming subscription renewals
   */
  async getUpcomingRenewals(daysAhead: number = 30): Promise<Array<{
    subscription_id: string
    provider: string
    amount: number
    currency: string
    billing_cycle: string
    renewal_date: string
    days_until_renewal: number
  }>> {
    const response = await apiClient.get('/notifications/upcoming-renewals', {
      params: { days_ahead: daysAhead }
    })
    return response.data
  },
}
