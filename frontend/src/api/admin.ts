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
}
