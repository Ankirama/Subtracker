import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { CancellationSuggestionBanner } from './CancellationSuggestionBanner'
import { renderWithProviders } from '@/test/renderWithProviders'
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
})
