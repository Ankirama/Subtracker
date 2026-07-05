import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useUncertainEmailsManagement } from './useUncertainEmailsManagement'
import { server } from '@/test/server'
import { createHookWrapper } from '@/test/hookWrapper'
import type { ManualSubscriptionCreate } from '@/types'

describe('useUncertainEmailsManagement', () => {
  it('loads an email detail and forwards it to the callback', async () => {
    const onEmailDetailLoaded = vi.fn()
    server.use(
      http.get('*/ai-sandbox/email/e1', () =>
        HttpResponse.json({ id: 'e1', subject: 'Hello' }),
      ),
    )

    const { result } = renderHook(
      () => useUncertainEmailsManagement({ onEmailDetailLoaded }),
      { wrapper: createHookWrapper() },
    )
    await act(async () => {
      await result.current.emailDetailMutation.mutateAsync('e1')
    })

    expect(onEmailDetailLoaded).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'e1' }),
    )
  })

  it('creates a subscription and fires the success callback', async () => {
    const onSubscriptionCreated = vi.fn()
    let postedBody: unknown = null
    server.use(
      http.post('*/ai-sandbox/create-subscription', async ({ request }) => {
        postedBody = await request.json()
        return HttpResponse.json({
          success: true,
          subscription_id: 'sub-1',
          message: 'created',
        })
      }),
    )

    const { result } = renderHook(
      () => useUncertainEmailsManagement({ onSubscriptionCreated }),
      { wrapper: createHookWrapper() },
    )
    const payload: ManualSubscriptionCreate = {
      email_id: 'e1',
      provider: 'Netflix',
    }
    await act(async () => {
      await result.current.createSubscriptionMutation.mutateAsync(payload)
    })

    expect(onSubscriptionCreated).toHaveBeenCalledTimes(1)
    expect(postedBody).toEqual(payload)
  })

  it('marks an email as not a subscription', async () => {
    const onMarkedNotSubscription = vi.fn()
    server.use(
      http.post('*/ai-sandbox/mark-not-subscription/e1', () =>
        HttpResponse.json({ success: true, message: 'ok' }),
      ),
    )

    const { result } = renderHook(
      () => useUncertainEmailsManagement({ onMarkedNotSubscription }),
      { wrapper: createHookWrapper() },
    )
    await act(async () => {
      await result.current.markNotSubscriptionMutation.mutateAsync('e1')
    })

    expect(onMarkedNotSubscription).toHaveBeenCalledTimes(1)
  })

  it('bulk-marks emails as not subscriptions', async () => {
    const onBulkMarked = vi.fn()
    server.use(
      http.post('*/ai-sandbox/bulk-mark-not-subscription', () =>
        HttpResponse.json({
          success: true,
          processed: 3,
          failed: 0,
          errors: [],
        }),
      ),
    )

    const { result } = renderHook(
      () => useUncertainEmailsManagement({ onBulkMarked }),
      { wrapper: createHookWrapper() },
    )
    await act(async () => {
      const response =
        await result.current.bulkMarkNotSubscriptionMutation.mutateAsync({
          email_ids: ['e1', 'e2', 'e3'],
        })
      expect(response.processed).toBe(3)
    })

    expect(onBulkMarked).toHaveBeenCalledTimes(1)
  })

  it('does not fire the success callback when creation fails', async () => {
    const onSubscriptionCreated = vi.fn()
    server.use(
      http.post('*/ai-sandbox/create-subscription', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    const { result } = renderHook(
      () => useUncertainEmailsManagement({ onSubscriptionCreated }),
      { wrapper: createHookWrapper() },
    )
    await act(async () => {
      await result.current.createSubscriptionMutation
        .mutateAsync({ email_id: 'e1', provider: 'Netflix' })
        .catch(() => undefined)
    })

    expect(onSubscriptionCreated).not.toHaveBeenCalled()
    expect(result.current.createSubscriptionMutation.isError).toBe(true)
  })
})
