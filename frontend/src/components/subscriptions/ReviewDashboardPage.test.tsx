import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse, delay } from 'msw'
import { ReviewDashboardPage } from './ReviewDashboardPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { ReviewSuggestion, ReviewSuggestionsResponse } from '@/types'

function buildSuggestion(overrides: Partial<ReviewSuggestion> = {}): ReviewSuggestion {
  return {
    subscription_id: 'sub-1',
    provider: 'Netflix',
    amount: 12.99,
    currency: 'USD',
    billing_cycle: 'monthly',
    reason: 'cancellation_detected',
    priority: 'high',
    message: 'AI detected a cancellation email for this subscription.',
    action_by_date: null,
    days_since_last_email: null,
    price_change_amount: null,
    price_change_date: null,
    dismissed_at: null,
    snoozed_until: null,
    ...overrides,
  }
}

function buildSuggestionsResponse(
  overrides: Partial<ReviewSuggestionsResponse> = {},
): ReviewSuggestionsResponse {
  const suggestions = overrides.suggestions ?? [
    buildSuggestion(),
    buildSuggestion({
      subscription_id: 'sub-2',
      provider: 'Spotify',
      reason: 'trial_ending',
      priority: 'critical',
      message: 'Trial ends today.',
    }),
  ]
  return {
    suggestions,
    total_count: suggestions.length,
    critical_count: suggestions.filter((s) => s.priority === 'critical').length,
    high_priority_count: suggestions.filter((s) => s.priority === 'high').length,
    ...overrides,
  }
}

describe('ReviewDashboardPage', () => {
  it('shows a loading spinner while the suggestions request is pending', () => {
    server.use(
      http.get('*/reviews/suggestions', async () => {
        await delay('infinite')
        return HttpResponse.json(buildSuggestionsResponse())
      }),
    )

    renderWithProviders(<ReviewDashboardPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows an error alert when the suggestions request fails', async () => {
    server.use(
      http.get('*/reviews/suggestions', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<ReviewDashboardPage />)

    expect(
      await screen.findByText('Failed to load review suggestions. Please try again.'),
    ).toBeInTheDocument()
  })
})
