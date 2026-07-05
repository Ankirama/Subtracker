import { describe, it, expect } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import {
  useAdminSyncErrors,
  useAdminSyncErrorDetail,
  useResolveAdminSyncError,
} from './useAdminSyncErrors'
import { server } from '@/test/server'
import { createHookWrapper } from '@/test/hookWrapper'

describe('useAdminSyncErrors', () => {
  it('fetches the admin sync errors list', async () => {
    server.use(
      http.get('*/admin/sync-errors', () =>
        HttpResponse.json({
          items: [{ id: 'se-1' }],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      ),
    )

    const { result } = renderHook(() => useAdminSyncErrors(), {
      wrapper: createHookWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.items[0].id).toBe('se-1')
  })
})

describe('useAdminSyncErrorDetail', () => {
  it('stays idle when the id is null', () => {
    const { result } = renderHook(() => useAdminSyncErrorDetail(null), {
      wrapper: createHookWrapper(),
    })

    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
  })

  it('fetches the detail when an id is provided', async () => {
    server.use(
      http.get('*/admin/sync-errors/se-1', () =>
        HttpResponse.json({ id: 'se-1', error_message: 'boom' }),
      ),
    )

    const { result } = renderHook(() => useAdminSyncErrorDetail('se-1'), {
      wrapper: createHookWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.error_message).toBe('boom')
  })
})

describe('useResolveAdminSyncError', () => {
  it('resolves a sync error by id', async () => {
    let resolvedId: string | null = null
    server.use(
      http.post('*/admin/sync-errors/se-1/resolve', () => {
        resolvedId = 'se-1'
        return HttpResponse.json({ id: 'se-1', status: 'resolved' })
      }),
    )

    const { result } = renderHook(() => useResolveAdminSyncError(), {
      wrapper: createHookWrapper(),
    })
    await act(async () => {
      await result.current.mutateAsync('se-1')
    })

    expect(resolvedId).toBe('se-1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})
