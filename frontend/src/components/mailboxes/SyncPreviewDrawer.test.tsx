import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { SyncPreviewDrawer } from './SyncPreviewDrawer'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type {
  NewSubscriptionPreview,
  SyncPreviewResponse,
} from '@/api/syncPreview'

const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }))
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateMock }
})

function buildNew(overrides: Partial<NewSubscriptionPreview> = {}): NewSubscriptionPreview {
  return {
    id: 'sub-1',
    provider: 'Netflix',
    custom_label: null,
    amount: 9.99,
    currency: 'EUR',
    billing_cycle: 'monthly',
    category: 'streaming',
    confidence_bucket: 'auto_saved',
    source_email_subject: 'Your receipt',
    source_email_date: null,
    ...overrides,
  }
}

function buildPreview(overrides: Partial<SyncPreviewResponse> = {}): SyncPreviewResponse {
  return {
    sync_history: {
      id: 'sh-1',
      mailbox_id: 'mbx-1',
      mailbox_email: 'me@acme.com',
      started_at: '2026-05-01T09:00:00Z',
      completed_at: '2026-05-01T10:00:00Z',
      new_emails_count: 1,
    },
    new_subscriptions: [buildNew()],
    updated_subscriptions: [],
    ...overrides,
  }
}

function mockPreview(preview: SyncPreviewResponse) {
  server.use(
    http.get('*/sync-history/sh-1/preview', () => HttpResponse.json(preview)),
  )
}

beforeEach(() => navigateMock.mockReset())

describe('SyncPreviewDrawer', () => {
  it('shows a loading spinner while the preview loads', () => {
    server.use(
      http.get('*/sync-history/sh-1/preview', async () => {
        await delay('infinite')
        return HttpResponse.json(buildPreview())
      }),
    )

    renderWithProviders(
      <SyncPreviewDrawer syncHistoryId="sh-1" isOpen onClose={vi.fn()} />,
      { withAuth: false },
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the new subscription cards', async () => {
    mockPreview(buildPreview())

    renderWithProviders(
      <SyncPreviewDrawer syncHistoryId="sh-1" isOpen onClose={vi.fn()} />,
      { withAuth: false },
    )

    expect(
      await screen.findByRole('heading', { name: 'New subscriptions' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Netflix')).toBeInTheDocument()
    expect(screen.getByText('Auto-saved')).toBeInTheDocument()
  })

  it('shows the empty state when nothing changed', async () => {
    mockPreview(
      buildPreview({ new_subscriptions: [], updated_subscriptions: [] }),
    )

    renderWithProviders(
      <SyncPreviewDrawer syncHistoryId="sh-1" isOpen onClose={vi.fn()} />,
      { withAuth: false },
    )

    expect(
      await screen.findByText('Nothing new this run.'),
    ).toBeInTheDocument()
  })

  it('navigates to the subscription and closes when a card is clicked', async () => {
    const onClose = vi.fn()
    mockPreview(buildPreview())
    const user = userEvent.setup()

    renderWithProviders(
      <SyncPreviewDrawer syncHistoryId="sh-1" isOpen onClose={onClose} />,
      { withAuth: false },
    )
    await screen.findByText('Netflix')

    await user.click(screen.getByText('Netflix'))

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(navigateMock).toHaveBeenCalledWith('/subscriptions/sub-1')
  })

  it('renders nothing when closed', () => {
    mockPreview(buildPreview())

    renderWithProviders(
      <SyncPreviewDrawer syncHistoryId="sh-1" isOpen={false} onClose={vi.fn()} />,
      { withAuth: false },
    )

    expect(screen.queryByText('Sync preview')).not.toBeInTheDocument()
  })
})
