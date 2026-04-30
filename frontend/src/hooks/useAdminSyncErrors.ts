import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  AdminSyncErrorListParams,
  adminSyncErrorsAPI,
} from '../api/adminSyncErrors'

export function useAdminSyncErrors(params: AdminSyncErrorListParams = {}) {
  return useQuery({
    queryKey: ['admin-sync-errors', params],
    queryFn: () => adminSyncErrorsAPI.list(params),
  })
}

export function useAdminSyncErrorDetail(id: string | null) {
  return useQuery({
    queryKey: ['admin-sync-errors', 'detail', id],
    queryFn: () => adminSyncErrorsAPI.detail(id ?? ''),
    enabled: !!id,
  })
}

export function useResolveAdminSyncError() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => adminSyncErrorsAPI.resolve(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['admin-sync-errors'] }),
  })
}
