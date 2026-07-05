import { describe, it, expect } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import {
  useSyncErrors,
  useIgnoreSyncError,
  useRetrySyncErrors,
} from './useSyncErrors'
import { server } from '@/test/server'
import { createHookWrapper } from '@/test/hookWrapper'

describe('useSyncErrors', () => {
  it('fetches the sync errors for a mailbox', async () => {
    server.use(
      http.get('*/mailboxes/mbx-1/sync-errors', () =>
        HttpResponse.json({
          items: [{ id: 'e1', error_type: 'extraction_failed' }],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      ),
    )

    const { result } = renderHook(() => useSyncErrors('mbx-1'), {
      wrapper: createHookWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.items[0].id).toBe('e1')
  })
})

describe('useIgnoreSyncError', () => {
  it('ignores a sync error by id', async () => {
    let ignoredId: string | null = null
    server.use(
      http.post('*/sync-errors/e1/ignore', () => {
        ignoredId = 'e1'
        return HttpResponse.json({ id: 'e1', status: 'ignored' })
      }),
    )

    const { result } = renderHook(() => useIgnoreSyncError('mbx-1'), {
      wrapper: createHookWrapper(),
    })
    await act(async () => {
      await result.current.mutateAsync('e1')
    })

    expect(ignoredId).toBe('e1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})

describe('useRetrySyncErrors', () => {
  it('retries the pending errors for a mailbox', async () => {
    server.use(
      http.post('*/mailboxes/mbx-1/sync-errors/retry', () =>
        HttpResponse.json({ task_id: 't1', pending_count: 3 }),
      ),
    )

    const { result } = renderHook(() => useRetrySyncErrors('mbx-1'), {
      wrapper: createHookWrapper(),
    })
    await act(async () => {
      const response = await result.current.mutateAsync()
      expect(response.task_id).toBe('t1')
      expect(response.pending_count).toBe(3)
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})
