import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

  it('renders suggestion cards including the cancellation_detected reason label', async () => {
    server.use(
      http.get('*/reviews/suggestions', () =>
        HttpResponse.json(buildSuggestionsResponse()),
      ),
    )

    renderWithProviders(<ReviewDashboardPage />)

    expect(
      await screen.findByRole('heading', { name: 'Smart Review Dashboard' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Netflix')).toBeInTheDocument()
    expect(screen.getByText('Spotify')).toBeInTheDocument()
    expect(screen.getAllByText('Cancellation Detected')).toHaveLength(2) // option + badge
    expect(screen.getByText('Showing 2 of 2 suggestions')).toBeInTheDocument()
  })

  it('filters suggestions when the Reason select is changed', async () => {
    server.use(
      http.get('*/reviews/suggestions', () =>
        HttpResponse.json(buildSuggestionsResponse()),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<ReviewDashboardPage />)
    await screen.findByText('Netflix')

    // Two <Select>s render: Priority is first in DOM order
    // (ReviewDashboardPage.tsx:270), Reason is second (:288).
    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[1], 'cancellation_detected')

    expect(screen.getByText('Netflix')).toBeInTheDocument()
    expect(screen.queryByText('Spotify')).not.toBeInTheDocument()
    expect(screen.getByText('Showing 1 of 2 suggestions')).toBeInTheDocument()
  })

  it('shows the "All good!" empty state when there are no suggestions', async () => {
    server.use(
      http.get('*/reviews/suggestions', () =>
        HttpResponse.json(
          buildSuggestionsResponse({ suggestions: [], total_count: 0 }),
        ),
      ),
    )

    renderWithProviders(<ReviewDashboardPage />)

    expect(await screen.findByText('All good! 🎉')).toBeInTheDocument()
  })
})
