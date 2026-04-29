import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  syncErrorsAPI,
  SyncErrorListParams,
} from '../api/syncErrors'

const KEY = (mailboxId: string, params: SyncErrorListParams) => [
  'sync-errors',
  mailboxId,
  params,
]

export function useSyncErrors(
  mailboxId: string,
  params: SyncErrorListParams = {},
) {
  return useQuery({
    queryKey: KEY(mailboxId, params),
    queryFn: () => syncErrorsAPI.list(mailboxId, params),
    staleTime: 10_000,
  })
}

export function useIgnoreSyncError(mailboxId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (errorId: string) => syncErrorsAPI.ignore(errorId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['sync-errors', mailboxId] }),
  })
}

export function useRetrySyncErrors(mailboxId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => syncErrorsAPI.retry(mailboxId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['sync-errors', mailboxId] }),
  })
}
