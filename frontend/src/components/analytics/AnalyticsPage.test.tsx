import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AnalyticsPage } from './AnalyticsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type {
  SubscriptionStats,
  AnalyticsResponse,
  SubscriptionListResponse,
} from '@/types'

const stats: SubscriptionStats = {
  total_subscriptions: 8,
  active_subscriptions: 5,
  total_monthly_cost: 42.5,
  total_yearly_cost: 510,
  by_category: {
    streaming: { count: 2, total: 25 },
    software: { count: 1, total: 17.5 },
  },
  by_billing_cycle: { monthly: 4, yearly: 1 },
  upcoming_renewals: [],
}

const analytics: AnalyticsResponse = {
  monthly_spending: [
    {
      month: 'Jan 2026',
      total_cost: 40,
      subscription_count: 5,
      new_subscriptions: 1,
      cancelled_subscriptions: 0,
    },
    {
      month: 'Feb 2026',
      total_cost: 45,
      subscription_count: 5,
      new_subscriptions: 0,
      cancelled_subscriptions: 0,
    },
  ],
  average_monthly_cost: 42.5,
  total_spent: 85,
  peak_month: 'Feb 2026',
  peak_month_cost: 45,
}

const subs = {
  subscriptions: [
    { provider: 'Netflix', amount: 15.99 },
    { provider: 'Spotify', amount: 9.99 },
  ],
  total: 2,
} as unknown as SubscriptionListResponse

function mockApis(
  overrides: {
    stats?: SubscriptionStats
    analytics?: AnalyticsResponse
    subs?: SubscriptionListResponse
  } = {},
) {
  server.use(
    http.get('*/subscriptions/stats', () =>
      HttpResponse.json(overrides.stats ?? stats),
    ),
    http.get('*/subscriptions/analytics/trends', () =>
      HttpResponse.json(overrides.analytics ?? analytics),
    ),
    http.get('*/subscriptions', () => HttpResponse.json(overrides.subs ?? subs)),
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AnalyticsPage', () => {
  it('shows a loading spinner while the stats request is pending', () => {
    server.use(
      http.get('*/subscriptions/stats', async () => {
        await delay('infinite')
        return HttpResponse.json(stats)
      }),
      http.get('*/subscriptions/analytics/trends', () =>
        HttpResponse.json(analytics),
      ),
      http.get('*/subscriptions', () => HttpResponse.json(subs)),
    )

    renderWithProviders(<AnalyticsPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows an error alert when the stats request fails', async () => {
    server.use(
      http.get('*/subscriptions/stats', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
      http.get('*/subscriptions/analytics/trends', () =>
        HttpResponse.json(analytics),
      ),
      http.get('*/subscriptions', () => HttpResponse.json(subs)),
    )

    renderWithProviders(<AnalyticsPage />)

    expect(
      await screen.findByText(
        'Failed to load analytics data. Please try again.',
      ),
    ).toBeInTheDocument()
  })

  it('renders the key metrics, chart sections, and category details', async () => {
    mockApis()

    renderWithProviders(<AnalyticsPage />)

    expect(
      await screen.findByRole('heading', { name: 'Analytics & Insights' }),
    ).toBeInTheDocument()
    // Key metric cards.
    expect(screen.getByText('Monthly Average')).toBeInTheDocument()
    expect(screen.getByText('Most Expensive')).toBeInTheDocument()
    expect(screen.getByText('Netflix')).toBeInTheDocument() // highest amount
    // Chart section headings.
    expect(
      screen.getByRole('heading', { name: 'Monthly Spending Trend' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Spending by Category' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Category Details' }),
    ).toBeInTheDocument()
    // Category names (capitalized from the by_category keys) appear in the
    // Category Details list; 'Streaming' is also echoed in the insights text.
    expect(screen.getAllByText('Streaming').length).toBeGreaterThan(0)
    expect(screen.getByText('Software')).toBeInTheDocument()
  })

  it('shows the empty state when there is no subscription data', async () => {
    mockApis({
      stats: {
        ...stats,
        total_monthly_cost: 0,
        by_category: {},
        by_billing_cycle: {},
      },
      subs: { subscriptions: [], total: 0 } as unknown as SubscriptionListResponse,
    })

    renderWithProviders(<AnalyticsPage />)

    expect(
      await screen.findByText('No subscription data available'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Add subscriptions to see personalized insights and recommendations',
      ),
    ).toBeInTheDocument()
  })

  it('refetches analytics with the selected time range', async () => {
    let lastMonths: string | null = null
    server.use(
      http.get('*/subscriptions/stats', () => HttpResponse.json(stats)),
      http.get('*/subscriptions', () => HttpResponse.json(subs)),
      http.get('*/subscriptions/analytics/trends', ({ request }) => {
        lastMonths = new URL(request.url).searchParams.get('months')
        return HttpResponse.json(analytics)
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AnalyticsPage />)
    await screen.findByRole('heading', { name: 'Analytics & Insights' })
    expect(lastMonths).toBe('6') // default is 6 months

    await user.selectOptions(
      screen.getByRole('combobox'),
      '3m',
    )

    await waitFor(() => expect(lastMonths).toBe('3'))
  })

  it('exports analytics to CSV', async () => {
    mockApis()
    // jsdom's URL lacks createObjectURL; define it without replacing the whole
    // URL global (which new URL() / MSW still need).
    const createObjectURL = vi.fn(() => 'blob:mock')
    ;(URL as unknown as { createObjectURL: unknown }).createObjectURL =
      createObjectURL
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    const user = userEvent.setup()

    renderWithProviders(<AnalyticsPage />)
    await screen.findByRole('heading', { name: 'Analytics & Insights' })

    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(createObjectURL).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
  })
})
