import apiClient from './client'

export interface AdminSetting {
  id: string
  key: string
  value: any
  value_type: 'string' | 'number' | 'boolean' | 'json'
  is_secret: boolean
  description?: string
  category?: string
  updated_by?: string
  created_at: string
  updated_at: string
}

export interface AdminSettingCreate {
  key: string
  value: any
  value_type: 'string' | 'number' | 'boolean' | 'json'
  is_secret?: boolean
  description?: string
  category?: string
}

export interface AdminSettingUpdate {
  value?: any
  value_type?: 'string' | 'number' | 'boolean' | 'json'
  is_secret?: boolean
  description?: string
  category?: string
}

export interface AdminSettingListResponse {
  items: AdminSetting[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SystemAnnouncementCreate {
  title: string
  message: string
  priority: 'low' | 'medium' | 'high'
  target_all_users: boolean
  target_user_ids?: string[]
}

export interface SystemAnnouncementResponse {
  success: boolean
  announcement_id: string
  notifications_created: number
  emails_sent: number
  message: string
}

// User Management Types
export interface User {
  id: string
  email: string
  is_active: boolean
  is_admin: boolean
  email_verified: boolean
  created_at: string
  updated_at: string
}

export interface UserDetail extends User {
  settings: Record<string, any>
  subscription_count: number
  mailbox_count: number
}

export interface UserStats {
  total_users: number
  active_users: number
  inactive_users: number
  admin_users: number
  new_users_30d: number
}

export interface UserListResponse {
  users: User[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface UserUpdateRequest {
  is_active?: boolean
  is_admin?: boolean
}

// Log Management Types
export interface LogEntry {
  id: string
  timestamp: string
  level: string
  module: string
  message: string
  source: string
}

export interface LogListResponse {
  logs: LogEntry[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Security Event Management Types
export interface SecurityEvent {
  id: string
  event_type: string
  user_id?: string
  ip_address?: string
  user_agent?: string
  details?: Record<string, any>
  severity?: 'low' | 'medium' | 'high' | 'critical'
  is_resolved: boolean
  resolved_at?: string
  created_at: string
}

export interface SecurityEventUpdate {
  is_resolved?: boolean
  resolved_at?: string
}

export interface SecurityEventListResponse {
  items: SecurityEvent[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SecurityStats {
  total_events: number
  unresolved_events: number
  events_24h: number
  critical_unresolved: number
  by_severity: {
    low: number
    medium: number
    high: number
    critical: number
  }
}

// Invite Management Types
export interface Invite {
  id: string
  token: string
  invite_url: string
  invited_email?: string
  note?: string
  is_used: boolean
  used_at?: string
  expires_at: string
  created_at: string
}

export interface InviteCreate {
  email?: string
  note?: string
  expires_in_days?: number
}

export interface InviteListResponse {
  invites: Invite[]
}

// Waitlist Management Types
export interface WaitlistEntry {
  id: string
  email: string
  status: 'pending' | 'approved' | 'rejected'
  access_code?: string
  created_at: string
  approved_at?: string
  rejected_at?: string
}

export interface WaitlistApproveRequest {
  send_email?: boolean
}

export interface WaitlistRejectRequest {
  reason?: string
}

export interface WaitlistApproveResponse {
  success: boolean
  message: string
  access_code?: string
}

export interface WaitlistListResponse {
  items: WaitlistEntry[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// IP Whitelist Management Types
export interface IPWhitelistEntry {
  ip_address: string
  description?: string
  added_by_user_id: string
  added_at: string
  last_seen?: string
  access_count: number
}

export interface IPWhitelistCreate {
  ip_address: string
  description?: string
}

export interface IPWhitelistUpdate {
  description?: string
}

export interface IPWhitelistListResponse {
  items: IPWhitelistEntry[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Configuration Status Types
export interface ConfigIssueItem {
  key: string
  category: string
  issues?: string[]
  required?: boolean
  description?: string
  current_value?: any
  env_value?: any
}

export interface ConfigStatusResponse {
  total_expected: number
  total_found: number
  valid_count: number
  incomplete_count: number
  missing_count: number
  extra_count: number
  missing: ConfigIssueItem[]
  incomplete: ConfigIssueItem[]
  valid: Array<{ key: string; category: string }>
  extra: Array<{ key: string; category: string; value_type: string }>
  is_healthy: boolean
  recommendations: string[]
}

export const adminApi = {
  // Admin Settings
  async listSettings(params?: {
    category?: string
    search?: string
    page?: number
    page_size?: number
  }): Promise<AdminSettingListResponse> {
    const response = await apiClient.get('/admin/config', { params })
    return response.data
  },

  async getSetting(key: string, decrypt: boolean = true): Promise<AdminSetting> {
    const response = await apiClient.get(`/admin/config/${key}`, {
      params: { decrypt },
    })
    return response.data
  },

  async createSetting(data: AdminSettingCreate): Promise<AdminSetting> {
    const response = await apiClient.post('/admin/config', data)
    return response.data
  },

  async updateSetting(
    key: string,
    data: AdminSettingUpdate
  ): Promise<AdminSetting> {
    const response = await apiClient.put(`/admin/config/${key}`, data)
    return response.data
  },

  async deleteSetting(key: string): Promise<void> {
    await apiClient.delete(`/admin/config/${key}`)
  },

  async getConfigStatus(): Promise<ConfigStatusResponse> {
    const response = await apiClient.get('/admin/config/status')
    return response.data
  },

  // System Announcements
  async broadcastAnnouncement(
    data: SystemAnnouncementCreate
  ): Promise<SystemAnnouncementResponse> {
    const response = await apiClient.post('/admin/announcements/broadcast', data)
    return response.data
  },

  // User Management
  async listUsers(params?: {
    page?: number
    page_size?: number
    search?: string
    is_active?: boolean
    is_admin?: boolean
  }): Promise<UserListResponse> {
    const response = await apiClient.get('/admin/users', { params })
    return response.data
  },

  async getUser(userId: string): Promise<UserDetail> {
    const response = await apiClient.get(`/admin/users/${userId}`)
    return response.data
  },

  async updateUser(userId: string, data: UserUpdateRequest): Promise<UserDetail> {
    const response = await apiClient.put(`/admin/users/${userId}`, data)
    return response.data
  },

  async deleteUser(userId: string): Promise<void> {
    await apiClient.delete(`/admin/users/${userId}`)
  },

  async getUserStats(): Promise<UserStats> {
    const response = await apiClient.get('/admin/users/stats')
    return response.data
  },

  async verifyUser(userId: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/admin/users/${userId}/verify`)
    return response.data
  },

  // Log Management
  async getLogs(params?: {
    page?: number
    page_size?: number
    level?: string
    search?: string
    source?: string
  }): Promise<LogListResponse> {
    const response = await apiClient.get('/admin/logs', { params })
    return response.data
  },

  async getLogStats(): Promise<{
    errors_24h: number
    warnings_24h: number
    total_logs: number
  }> {
    const response = await apiClient.get('/admin/logs/stats')
    return response.data
  },

  async getLogSources(): Promise<{
    sources: Array<{ name: string; label: string; available: boolean }>
  }> {
    const response = await apiClient.get('/admin/logs/sources')
    return response.data
  },

  // Security Events Management
  async listSecurityEvents(params?: {
    page?: number
    page_size?: number
    event_type?: string
    severity?: string
    is_resolved?: boolean
  }): Promise<SecurityEventListResponse> {
    const response = await apiClient.get('/admin/security', { params })
    return response.data
  },

  async getSecurityEvent(eventId: string): Promise<SecurityEvent> {
    const response = await apiClient.get(`/admin/security/${eventId}`)
    return response.data
  },

  async updateSecurityEvent(
    eventId: string,
    data: SecurityEventUpdate
  ): Promise<SecurityEvent> {
    const response = await apiClient.patch(`/admin/security/${eventId}`, data)
    return response.data
  },

  async deleteSecurityEvent(eventId: string): Promise<void> {
    await apiClient.delete(`/admin/security/${eventId}`)
  },

  async getSecurityStats(): Promise<SecurityStats> {
    const response = await apiClient.get('/admin/security/stats')
    return response.data
  },

  async getEventTypes(): Promise<{
    event_types: string[]
  }> {
    const response = await apiClient.get('/admin/security/event-types')
    return response.data
  },

  // IP Whitelist Management
  async listIPWhitelist(params?: {
    page?: number
    page_size?: number
  }): Promise<IPWhitelistListResponse> {
    const response = await apiClient.get('/admin/security/ip-whitelist', { params })
    return response.data
  },

  async getIPWhitelistEntry(ipAddress: string): Promise<IPWhitelistEntry> {
    const response = await apiClient.get(`/admin/security/ip-whitelist/${encodeURIComponent(ipAddress)}`)
    return response.data
  },

  async addIPToWhitelist(data: IPWhitelistCreate): Promise<IPWhitelistEntry> {
    const response = await apiClient.post('/admin/security/ip-whitelist', data)
    return response.data
  },

  async updateIPWhitelistEntry(
    ipAddress: string,
    data: IPWhitelistUpdate
  ): Promise<IPWhitelistEntry> {
    const response = await apiClient.patch(`/admin/security/ip-whitelist/${encodeURIComponent(ipAddress)}`, data)
    return response.data
  },

  async removeIPFromWhitelist(ipAddress: string): Promise<void> {
    await apiClient.delete(`/admin/security/ip-whitelist/${encodeURIComponent(ipAddress)}`)
  },

  // Invite Management
  async listInvites(): Promise<InviteListResponse> {
    const response = await apiClient.get('/admin/invites')
    return response.data
  },

  async createInvite(data: InviteCreate): Promise<Invite> {
    const response = await apiClient.post('/admin/invites', data)
    return response.data
  },

  async revokeInvite(inviteId: string): Promise<void> {
    await apiClient.delete(`/admin/invites/${inviteId}`)
  },

  // Waitlist Management
  async listWaitlist(params?: {
    page?: number
    page_size?: number
    status_filter?: 'pending' | 'approved' | 'rejected'
  }): Promise<WaitlistListResponse> {
    const response = await apiClient.get('/admin/waitlist', { params })
    return response.data
  },

  async approveWaitlist(
    entryId: string,
    data: WaitlistApproveRequest
  ): Promise<WaitlistApproveResponse> {
    const response = await apiClient.post(`/admin/waitlist/${entryId}/approve`, data)
    return response.data
  },

  async rejectWaitlist(
    entryId: string,
    data: WaitlistRejectRequest
  ): Promise<void> {
    await apiClient.post(`/admin/waitlist/${entryId}/reject`, data)
  },

  async deleteWaitlist(entryId: string): Promise<void> {
    await apiClient.delete(`/admin/waitlist/${entryId}`)
  },
}
