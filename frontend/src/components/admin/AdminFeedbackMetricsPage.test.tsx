import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import { http, HttpResponse, delay } from 'msw'
import { AdminFeedbackMetricsPage } from './AdminFeedbackMetricsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { DashboardMetrics, ProviderMetrics } from '@/types'

function buildProvider(overrides: Partial<ProviderMetrics> = {}): ProviderMetrics {
  return {
    provider_name: 'Netflix',
    total_feedback: 30,
    helpful_count: 20,
    not_helpful_count: 10,
    success_rate: 0.85,
    avg_time_minutes: 5.2,
    avg_helpfulness: 4.3,
    avg_accuracy: 3.8,
    common_issues: ['outdated link', 'wrong price'],
    ...overrides,
  }
}

function buildMetrics(overrides: Partial<DashboardMetrics> = {}): DashboardMetrics {
  return {
    overall_metrics: {
      total_feedback: 120,
      high_confidence_success_rate: 0.92,
      low_confidence_success_rate: 0.55,
      accuracy_improvement_over_time: null,
      providers_needing_update: ['netflix'],
    },
    provider_metrics: [buildProvider()],
    ...overrides,
  }
}

function mockMetrics(metrics: DashboardMetrics) {
  server.use(
    http.get('*/feedback/metrics/dashboard', () => HttpResponse.json(metrics)),
  )
}

describe('AdminFeedbackMetricsPage', () => {
  it('shows a loading spinner while metrics are being fetched', () => {
    server.use(
      http.get('*/feedback/metrics/dashboard', async () => {
        await delay('infinite')
        return HttpResponse.json(buildMetrics())
      }),
    )

    renderWithProviders(<AdminFeedbackMetricsPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the overall metrics and the provider performance row', async () => {
    mockMetrics(buildMetrics())

    renderWithProviders(<AdminFeedbackMetricsPage />)

    expect(
      await screen.findByRole('heading', { name: 'Feedback & Validation Metrics' }),
    ).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
    expect(screen.getByText('92.0%')).toBeInTheDocument()
    const providerRow = within(
      screen.getByText('Netflix').closest('tr') as HTMLElement,
    )
    expect(providerRow.getByText('85.0%')).toBeInTheDocument()
    expect(providerRow.getByText('4.3/5')).toBeInTheDocument()
  })

  it('shows the error state when metrics fail to load', async () => {
    server.use(
      http.get('*/feedback/metrics/dashboard', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<AdminFeedbackMetricsPage />)

    expect(await screen.findByText('Failed to load metrics')).toBeInTheDocument()
  })

  it('lists the providers needing review', async () => {
    mockMetrics(
      buildMetrics({
        overall_metrics: {
          total_feedback: 50,
          high_confidence_success_rate: 0.9,
          low_confidence_success_rate: 0.4,
          accuracy_improvement_over_time: null,
          providers_needing_update: ['netflix', 'spotify'],
        },
      }),
    )

    renderWithProviders(<AdminFeedbackMetricsPage />)

    expect(await screen.findByText('Providers Needing Review')).toBeInTheDocument()
    expect(screen.getByText('netflix')).toBeInTheDocument()
    expect(screen.getByText('spotify')).toBeInTheDocument()
  })

  it('shows the empty table state when there is no provider data', async () => {
    mockMetrics(
      buildMetrics({
        overall_metrics: {
          total_feedback: 0,
          high_confidence_success_rate: null,
          low_confidence_success_rate: null,
          accuracy_improvement_over_time: null,
          providers_needing_update: [],
        },
        provider_metrics: [],
      }),
    )

    renderWithProviders(<AdminFeedbackMetricsPage />)

    expect(await screen.findByText('No provider data yet')).toBeInTheDocument()
  })
})
