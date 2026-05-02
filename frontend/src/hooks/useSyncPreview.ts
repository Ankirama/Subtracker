import { useQuery } from '@tanstack/react-query'
import { syncPreviewAPI } from '../api/syncPreview'

export function useSyncPreview(syncHistoryId: string | null) {
  return useQuery({
    queryKey: ['sync-preview', syncHistoryId],
    queryFn: () => syncPreviewAPI.get(syncHistoryId ?? ''),
    enabled: !!syncHistoryId,
    staleTime: 60_000,
  })
}
