import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import { http, HttpResponse, delay } from 'msw'
import { SyncErrorsPage } from './SyncErrorsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { SyncError } from '@/api/syncErrors'

function buildError(overrides: Partial<SyncError> = {}): SyncError {
  return {
    id: 'e1',
    mailbox_id: 'mbx-1',
    sync_history_id: null,
    provider_message_id: null,
    subject: 'Your invoice',
    sender: 'billing@acme.com',
    error_type: 'extraction_failed',
    error_message: 'boom',
    severity: 'high',
    status: 'pending',
    resolution: null,
    retry_count: 0,
    last_retry_at: null,
    created_at: '2026-05-01T10:00:00Z',
    updated_at: '2026-05-01T10:00:00Z',
    ...overrides,
  }
}

function listResponse(items: SyncError[]) {
  return { items, total: items.length, page: 1, page_size: 50, total_pages: 1 }
}

function mockList(items: SyncError[]) {
  server.use(
    http.get('*/mailboxes/mbx-1/sync-errors', () =>
      HttpResponse.json(listResponse(items)),
    ),
  )
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/mailboxes/:mailboxId/errors" element={<SyncErrorsPage />} />
    </Routes>,
    { route: '/mailboxes/mbx-1/errors' },
  )
}

function row(text: string) {
  return within(screen.getByText(text).closest('tr') as HTMLElement)
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('SyncErrorsPage', () => {
  it('shows a loading spinner while errors are being fetched', () => {
    server.use(
      http.get('*/mailboxes/mbx-1/sync-errors', async () => {
        await delay('infinite')
        return HttpResponse.json(listResponse([]))
      }),
    )

    renderPage()

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the skipped emails', async () => {
    mockList([buildError()])

    renderPage()

    // The heading renders before data loads; wait for a data-dependent row.
    await screen.findByText('billing@acme.com')
    expect(
      screen.getByRole('heading', { name: 'Skipped emails' }),
    ).toBeInTheDocument()
    expect(row('billing@acme.com').getByText('extraction_failed')).toBeInTheDocument()
  })

  it('shows the empty state when there are no errors', async () => {
    mockList([])

    renderPage()

    expect(
      await screen.findByText('No skipped emails — your sync is clean.'),
    ).toBeInTheDocument()
  })

  it('retries all pending errors', async () => {
    let retried = false
    mockList([buildError()])
    server.use(
      http.post('*/mailboxes/mbx-1/sync-errors/retry', () => {
        retried = true
        return HttpResponse.json({ task_id: 't1', pending_count: 1 })
      }),
    )
    const user = userEvent.setup()

    renderPage()
    await screen.findByText('billing@acme.com')

    await user.click(screen.getByRole('button', { name: 'Retry all pending' }))

    expect(
      await screen.findByText('Retry queued. Refresh in a few seconds.'),
    ).toBeInTheDocument()
    expect(retried).toBe(true)
  })

  it('ignores a pending error after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    let ignoredId: string | null = null
    mockList([buildError()])
    server.use(
      http.post('*/sync-errors/e1/ignore', () => {
        ignoredId = 'e1'
        return HttpResponse.json(buildError({ status: 'ignored' }))
      }),
    )
    const user = userEvent.setup()

    renderPage()
    await screen.findByText('billing@acme.com')

    await user.click(row('billing@acme.com').getByRole('button', { name: 'Ignore' }))

    expect(await screen.findByText('Marked as ignored.')).toBeInTheDocument()
    expect(ignoredId).toBe('e1')
  })

  it('filters the errors by status', async () => {
    server.use(
      http.get('*/mailboxes/mbx-1/sync-errors', ({ request }) => {
        const status = new URL(request.url).searchParams.get('status')
        if (status === 'ignored') {
          return HttpResponse.json(
            listResponse([
              buildError({ id: 'e2', status: 'ignored', sender: 'ignored@acme.com' }),
            ]),
          )
        }
        return HttpResponse.json(listResponse([buildError()]))
      }),
    )
    const user = userEvent.setup()

    renderPage()
    await screen.findByText('billing@acme.com')

    // The status filter is the first of the two selects.
    await user.selectOptions(screen.getAllByRole('combobox')[0], 'ignored')

    expect(await screen.findByText('ignored@acme.com')).toBeInTheDocument()
    expect(screen.queryByText('billing@acme.com')).not.toBeInTheDocument()
  })
})
