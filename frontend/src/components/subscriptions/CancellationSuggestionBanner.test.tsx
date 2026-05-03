import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { CancellationSuggestionBanner } from './CancellationSuggestionBanner'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Subscription } from '@/types'

function buildSubscriptionWithSuggestion(
  overrides: Partial<Subscription> = {},
): Subscription {
  return {
    id: 'sub-1',
    user_id: 'test-user-id',
    mailbox_id: null,
    provider: 'Netflix',
    email_sender: null,
    amount: 12.99,
    currency: 'USD',
    billing_cycle: 'monthly',
    renewal_date: null,
    next_renewal_date: null,
    next_billing_date: null,
    is_active: true,
    category: 'streaming',
    tags: null,
    custom_label: null,
    notes: null,
    confidence_score: 0.95,
    extraction_method: 'ai',
    payment_processor: null,
    first_detected_at: '2026-01-01T00:00:00Z',
    last_confirmed_at: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    suggested_cancellation_status: 'cancelled',
    cancellation_suggestion_reason: 'Email confirms cancellation processed.',
    cancellation_suggestion_created_at: '2026-04-30T00:00:00Z',
    ...overrides,
  }
}

describe('CancellationSuggestionBanner', () => {
  it('renders nothing when no cancellation suggestion exists', () => {
    const subscription = buildSubscriptionWithSuggestion({
      suggested_cancellation_status: null,
      cancellation_suggestion_reason: null,
    })

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={subscription}
        onUpdate={() => {}}
      />,
    )

    expect(
      screen.queryByText('AI Detected Potential Cancellation'),
    ).not.toBeInTheDocument()
  })

  it('renders the title, reason, and both action buttons when suggestion is present', () => {
    const subscription = buildSubscriptionWithSuggestion()

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={subscription}
        onUpdate={() => {}}
      />,
    )

    expect(
      screen.getByText('AI Detected Potential Cancellation'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Email confirms cancellation processed.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Accept & Mark as Cancelled' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Dismiss Suggestion' }),
    ).toBeInTheDocument()
  })

  it('calls accept-suggestion endpoint and onUpdate when Accept is clicked', async () => {
    server.use(
      http.post('*/subscriptions/sub-1/accept-suggestion', () =>
        HttpResponse.json(buildSubscriptionWithSuggestion()),
      ),
    )
    const onUpdate = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={buildSubscriptionWithSuggestion()}
        onUpdate={onUpdate}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Accept & Mark as Cancelled' }),
    )

    expect(await screen.findByText('Suggestion Accepted')).toBeInTheDocument()
    expect(onUpdate).toHaveBeenCalledTimes(1)
  })

  it('calls dismiss-suggestion endpoint, hides the banner, and fires onUpdate when Dismiss is clicked', async () => {
    server.use(
      http.post('*/subscriptions/sub-1/dismiss-suggestion', () =>
        HttpResponse.json({ success: true, message: 'dismissed' }),
      ),
    )
    const onUpdate = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <CancellationSuggestionBanner
        subscription={buildSubscriptionWithSuggestion()}
        onUpdate={onUpdate}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Dismiss Suggestion' }),
    )

    expect(await screen.findByText('Suggestion Dismissed')).toBeInTheDocument()
    expect(
      screen.queryByText('AI Detected Potential Cancellation'),
    ).not.toBeInTheDocument()
    expect(onUpdate).toHaveBeenCalledTimes(1)
  })
})
