import apiClient from './client'

export interface ExportFilters {
  startDate?: string
  endDate?: string
  activeOnly?: boolean
  category?: string
}

export const exportApi = {
  /**
   * Export subscriptions to CSV format
   */
  async exportCSV(filters?: ExportFilters): Promise<Blob> {
    const params = new URLSearchParams()
    if (filters?.startDate) params.append('start_date', filters.startDate)
    if (filters?.endDate) params.append('end_date', filters.endDate)
    if (filters?.activeOnly) params.append('active_only', 'true')
    if (filters?.category) params.append('category', filters.category)

    const response = await apiClient.get(`/export/csv?${params.toString()}`, {
      responseType: 'blob',
    })
    return response.data
  },

  /**
   * Export subscriptions to PDF format (opens in new tab)
   */
  async exportPDF(filters?: ExportFilters): Promise<void> {
    const params = new URLSearchParams()
    if (filters?.startDate) params.append('start_date', filters.startDate)
    if (filters?.endDate) params.append('end_date', filters.endDate)
    if (filters?.activeOnly) params.append('active_only', 'true')
    if (filters?.category) params.append('category', filters.category)

    // Get the auth token
    const token = localStorage.getItem('token')

    // Open PDF in new window with authorization
    const url = `${apiClient.defaults.baseURL}/export/pdf?${params.toString()}`
    const newWindow = window.open(url, '_blank')

    if (newWindow) {
      // Wait a moment and set the authorization header via fetch
      // This is a workaround since window.open doesn't support headers
      setTimeout(async () => {
        try {
          const response = await apiClient.get(`/export/pdf?${params.toString()}`, {
            responseType: 'text',
          })
          const blob = new Blob([response.data], { type: 'text/html' })
          const blobUrl = URL.createObjectURL(blob)
          newWindow.location.href = blobUrl
        } catch (error) {
          console.error('Failed to load PDF:', error)
        }
      }, 100)
    }
  },

  /**
   * Get analytics data for custom reporting
   */
  async getAnalyticsData(startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)

    const response = await apiClient.get(`/export/analytics?${params.toString()}`)
    return response.data
  },

  /**
   * Download CSV file helper
   */
  downloadCSV(blob: Blob, filename: string = `subscriptions_${new Date().toISOString().split('T')[0]}.csv`) {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  },
}
