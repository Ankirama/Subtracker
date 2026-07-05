import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { SubscriptionsPage } from './SubscriptionsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Subscription, SubscriptionListResponse } from '@/types'
import type { CategoriesListResponse } from '@/api/categories'

// A fixed timestamp well outside the 24h "recently added" window so fixtures
// don't accidentally flip isNewSubscription() (which compares to real now).
const OLD = '2020-01-01T00:00:00Z'

function buildSubscription(overrides: Partial<Subscription> = {}): Subscription {
  return {
    id: 'sub-1',
    user_id: 'user-1',
    mailbox_id: null,
    provider: 'Netflix',
    email_sender: null,
    amount: 12.99,
    currency: 'EUR',
    billing_cycle: 'monthly',
    renewal_date: '2026-08-01T00:00:00Z',
    next_renewal_date: '2026-08-01T00:00:00Z',
    next_billing_date: null,
    is_active: true,
    category: 'streaming',
    tags: null,
    custom_label: null,
    notes: null,
    confidence_score: 0.95,
    extraction_method: 'manual',
    payment_processor: null,
    first_detected_at: OLD,
    last_confirmed_at: OLD,
    created_at: OLD,
    updated_at: OLD,
    suggested_cancellation_status: null,
    cancellation_suggestion_reason: null,
    cancellation_suggestion_created_at: null,
    ...overrides,
  }
}

function buildListResponse(
  overrides: Partial<SubscriptionListResponse> = {},
): SubscriptionListResponse {
  const subscriptions = overrides.subscriptions ?? [
    buildSubscription(),
    buildSubscription({ id: 'sub-2', provider: 'Spotify' }),
  ]
  return {
    subscriptions,
    total: subscriptions.length,
    page: 1,
    page_size: 50,
    ...overrides,
  }
}

const emptyCategories: CategoriesListResponse = { categories: [], total: 0 }

/** Register the always-needed categories handler plus a subscriptions handler. */
function mockApis(subscriptionsHandler: Parameters<typeof http.get>[1]) {
  server.use(
    http.get('*/categories', () => HttpResponse.json(emptyCategories)),
    http.get('*/subscriptions', subscriptionsHandler),
  )
}

// The desktop table and mobile cards both mount in jsdom (responsive display is
// CSS-only), so provider names/action buttons appear twice. The desktop table
// resolves to display:none at the base breakpoint, hiding it from the a11y tree
// — hence { hidden: true } here and on role queries scoped to it below.
function table() {
  return within(screen.getByRole('table', { hidden: true }))
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('SubscriptionsPage', () => {
  it('shows a loading spinner while the subscriptions request is pending', () => {
    mockApis(async () => {
      await delay('infinite')
      return HttpResponse.json(buildListResponse())
    })

    renderWithProviders(<SubscriptionsPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows an error alert when the subscriptions request fails', async () => {
    mockApis(() => HttpResponse.json({ detail: 'boom' }, { status: 500 }))

    renderWithProviders(<SubscriptionsPage />)

    expect(
      await screen.findByText('Failed to load subscriptions. Please try again.'),
    ).toBeInTheDocument()
  })

  it('renders the subscriptions and the total count', async () => {
    mockApis(() => HttpResponse.json(buildListResponse()))

    renderWithProviders(<SubscriptionsPage />)

    expect(
      await screen.findByRole('heading', { name: 'Subscriptions' }),
    ).toBeInTheDocument()
    expect(screen.getByText('2 total subscriptions')).toBeInTheDocument()
    expect(table().getByText('Netflix')).toBeInTheDocument()
    expect(table().getByText('Spotify')).toBeInTheDocument()
  })

  it('filters the list by the search term', async () => {
    mockApis(() => HttpResponse.json(buildListResponse()))
    const user = userEvent.setup()

    renderWithProviders(<SubscriptionsPage />)
    // Wait for the data to load (header + table mount together) before
    // scoping to the table, which getByRole resolves synchronously.
    await screen.findByRole('heading', { name: 'Subscriptions' })

    await user.type(
      screen.getByPlaceholderText('Search subscriptions...'),
      'Netflix',
    )

    expect(table().getByText('Netflix')).toBeInTheDocument()
    expect(table().queryByText('Spotify')).not.toBeInTheDocument()
  })

  it('shows the empty state when no subscription matches the search', async () => {
    mockApis(() => HttpResponse.json(buildListResponse()))
    const user = userEvent.setup()

    renderWithProviders(<SubscriptionsPage />)
    // Wait for the data to load (header + table mount together) before
    // scoping to the table, which getByRole resolves synchronously.
    await screen.findByRole('heading', { name: 'Subscriptions' })

    await user.type(
      screen.getByPlaceholderText('Search subscriptions...'),
      'Disney',
    )

    expect(table().getByText('No subscriptions found')).toBeInTheDocument()
  })

  it('deletes a manually created subscription after confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    let deleteCalledFor: string | null = null
    mockApis(() =>
      HttpResponse.json(
        buildListResponse({ subscriptions: [buildSubscription()] }),
      ),
    )
    server.use(
      http.delete('*/subscriptions/sub-1', () => {
        deleteCalledFor = 'sub-1'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<SubscriptionsPage />)
    // Wait for the data to load (header + table mount together) before
    // scoping to the table, which getByRole resolves synchronously.
    await screen.findByRole('heading', { name: 'Subscriptions' })

    await user.click(table().getByRole('button', { name: 'Delete', hidden: true }))

    expect(confirmSpy).toHaveBeenCalled()
    expect(await screen.findByText('Subscription deleted')).toBeInTheDocument()
    expect(deleteCalledFor).toBe('sub-1')
  })

  it('triggers a status refresh and reports the result', async () => {
    mockApis(() => HttpResponse.json(buildListResponse()))
    server.use(
      http.post('*/subscriptions/update-status', () =>
        HttpResponse.json({
          success: true,
          total_activated: 2,
          total_deactivated: 1,
          mailboxes_updated: 1,
          message: 'ok',
        }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<SubscriptionsPage />)
    await screen.findByRole('heading', { name: 'Subscriptions' })

    await user.click(screen.getByRole('button', { name: /Refresh Status/i }))

    expect(
      await screen.findByText('Subscription statuses updated'),
    ).toBeInTheDocument()
    expect(screen.getByText('2 activated, 1 deactivated')).toBeInTheDocument()
  })
})
