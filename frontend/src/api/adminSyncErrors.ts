import apiClient from './client'
import { SyncError, SyncErrorListParams } from './syncErrors'

export interface AdminSyncError extends SyncError {
  stack_trace: string | null
  raw_payload: Record<string, unknown> | null
  resolved_at: string | null
  resolved_by_id: string | null
}

export interface AdminSyncErrorList {
  items: AdminSyncError[]
  total: number
  page: number
  page_size: number
}

export interface AdminSyncErrorListParams extends SyncErrorListParams {
  severity?: 'low' | 'medium' | 'high'
  mailbox_id?: string
}

export const adminSyncErrorsAPI = {
  list: async (
    params: AdminSyncErrorListParams = {},
  ): Promise<AdminSyncErrorList> => {
    const response = await apiClient.get<AdminSyncErrorList>(
      '/admin/sync-errors',
      { params },
    )
    return response.data
  },

  detail: async (id: string): Promise<AdminSyncError> => {
    const response = await apiClient.get<AdminSyncError>(
      `/admin/sync-errors/${id}`,
    )
    return response.data
  },

  resolve: async (id: string): Promise<AdminSyncError> => {
    const response = await apiClient.post<AdminSyncError>(
      `/admin/sync-errors/${id}/resolve`,
    )
    return response.data
  },
}
