import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useSyncPreview } from './useSyncPreview'
import { server } from '@/test/server'
import { createHookWrapper } from '@/test/hookWrapper'

describe('useSyncPreview', () => {
  it('stays idle while the sync history id is null', () => {
    const { result } = renderHook(() => useSyncPreview(null), {
      wrapper: createHookWrapper(),
    })

    // A disabled query never fetches.
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
  })

  it('fetches the preview when a sync history id is provided', async () => {
    server.use(
      http.get('*/sync-history/sh-1/preview', () =>
        HttpResponse.json({
          sync_history: { id: 'sh-1' },
          new_subscriptions: [{ provider: 'Netflix' }],
          updated_subscriptions: [],
        }),
      ),
    )

    const { result } = renderHook(() => useSyncPreview('sh-1'), {
      wrapper: createHookWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.new_subscriptions).toHaveLength(1)
  })
})
