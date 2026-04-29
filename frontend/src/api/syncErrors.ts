import apiClient from './client'

export type SyncErrorStatus =
  | 'pending'
  | 'retried'
  | 'resolved'
  | 'ignored'
  | 'auto_recovered'

export type SyncErrorType =
  | 'schema_too_long'
  | 'encoding_error'
  | 'extraction_failed'
  | 'db_constraint'
  | 'unexpected'

export type SyncErrorSeverity = 'low' | 'medium' | 'high'

export interface SyncError {
  id: string
  mailbox_id: string
  sync_history_id: string | null
  provider_message_id: string | null
  subject: string | null
  sender: string | null
  error_type: SyncErrorType
  error_message: string
  severity: SyncErrorSeverity
  status: SyncErrorStatus
  resolution: string | null
  retry_count: number
  last_retry_at: string | null
  created_at: string
  updated_at: string
}

export interface SyncErrorList {
  items: SyncError[]
  total: number
  page: number
  page_size: number
}

export interface RetryResponse {
  task_id: string
  pending_count: number
}

export interface SyncErrorListParams {
  status?: SyncErrorStatus
  error_type?: SyncErrorType
  page?: number
  page_size?: number
}

export const syncErrorsAPI = {
  list: async (
    mailboxId: string,
    params: SyncErrorListParams = {},
  ): Promise<SyncErrorList> => {
    const response = await apiClient.get<SyncErrorList>(
      `/mailboxes/${mailboxId}/sync-errors`,
      { params },
    )
    return response.data
  },

  ignore: async (errorId: string): Promise<SyncError> => {
    const response = await apiClient.post<SyncError>(
      `/sync-errors/${errorId}/ignore`,
    )
    return response.data
  },

  retry: async (mailboxId: string): Promise<RetryResponse> => {
    const response = await apiClient.post<RetryResponse>(
      `/mailboxes/${mailboxId}/sync-errors/retry`,
    )
    return response.data
  },
}
