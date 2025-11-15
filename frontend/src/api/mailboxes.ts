import apiClient from './client'
import {
  Mailbox,
  MailboxCreate,
  MailboxUpdate,
  MailboxSyncStatus,
  MailboxTestResult,
} from '../types'

export const mailboxesAPI = {
  getAll: async (): Promise<Mailbox[]> => {
    const response = await apiClient.get<Mailbox[]>('/mailboxes')
    return response.data
  },

  getById: async (id: string): Promise<Mailbox> => {
    const response = await apiClient.get<Mailbox>(`/mailboxes/${id}`)
    return response.data
  },

  create: async (data: MailboxCreate): Promise<Mailbox> => {
    const response = await apiClient.post<Mailbox>('/mailboxes', data)
    return response.data
  },

  update: async (id: string, data: MailboxUpdate): Promise<Mailbox> => {
    const response = await apiClient.put<Mailbox>(`/mailboxes/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/mailboxes/${id}`)
  },

  sync: async (id: string, params?: {
    force_full_sync?: boolean
    date_filter_override?: string
  }): Promise<MailboxSyncStatus> => {
    const response = await apiClient.post<MailboxSyncStatus>(`/mailboxes/${id}/sync`, params)
    return response.data
  },

  getSyncStatus: async (id: string): Promise<MailboxSyncStatus> => {
    const response = await apiClient.get<MailboxSyncStatus>(`/mailboxes/${id}/sync-status`)
    return response.data
  },

  testConnection: async (credentials: {
    server_url: string
    username: string
    password: string
  }): Promise<MailboxTestResult> => {
    const response = await apiClient.post<MailboxTestResult>('/mailboxes/test', {
      provider_type: 'jmap',
      credentials,
    })
    return response.data
  },
}
