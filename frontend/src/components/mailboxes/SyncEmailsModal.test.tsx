import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { SyncEmailsModal } from './SyncEmailsModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Mailbox } from '@/types'

function buildMailbox(overrides: Partial<Mailbox> = {}): Mailbox {
  return {
    id: 'mb-1',
    user_id: 'user-1',
    provider_type: 'gmail',
    email_address: 'me@example.com',
    display_name: 'Personal Gmail',
    is_active: true,
    last_sync_at: null,
    last_sync_status: null,
    last_sync_emails_processed: null,
    last_sync_subscriptions_found: null,
    last_sync_error_message: null,
    last_sync_oldest_email_date: null,
    last_sync_newest_email_date: null,
    last_sync_new_emails_count: null,
    last_sync_history_id: null,
    sync_frequency: 'daily',
    batch_size: 100,
    import_date_filter: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    needs_reconnect: false,
    auth_error_at: null,
    auth_error_message: null,
    pending_sync_errors_count: 0,
    ...overrides,
  }
}

// The modal starts polling getSyncStatus after a successful start; register a
// handler so any late poll doesn't hit onUnhandledRequest.
function mockSyncStatus(status = 'in_progress') {
  server.use(
    http.get('*/mailboxes/mb-1/sync-status', () =>
      HttpResponse.json({ status, total_emails_processed: 0, subscriptions_found: 0 }),
    ),
  )
}

describe('SyncEmailsModal', () => {
  it('renders the period selection and start controls', async () => {
    renderWithProviders(
      <SyncEmailsModal isOpen onClose={vi.fn()} mailbox={buildMailbox()} />,
    )

    expect(await screen.findByText('Sync Emails')).toBeInTheDocument()
    expect(screen.getByLabelText('Select Time Period')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start Sync' })).toBeInTheDocument()
  })

  it('reveals the custom days input when the custom period is selected', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SyncEmailsModal isOpen onClose={vi.fn()} mailbox={buildMailbox()} />,
    )
    await screen.findByText('Sync Emails')

    await user.selectOptions(screen.getByLabelText('Select Time Period'), 'custom')

    expect(screen.getByLabelText('Number of Days')).toBeInTheDocument()
  })

  it('starts a sync and shows in-progress status', async () => {
    mockSyncStatus('in_progress')
    server.use(
      http.post('*/mailboxes/mb-1/sync', () =>
        HttpResponse.json({
          status: 'in_progress',
          total_emails_processed: 0,
          subscriptions_found: 0,
        }),
      ),
    )
    const onSyncStarted = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <SyncEmailsModal
        isOpen
        onClose={vi.fn()}
        mailbox={buildMailbox()}
        onSyncStarted={onSyncStarted}
      />,
    )
    await screen.findByText('Sync Emails')

    await user.click(screen.getByRole('button', { name: 'Start Sync' }))

    expect(await screen.findByText('In Progress')).toBeInTheDocument()
    expect(onSyncStarted).toHaveBeenCalled()
  })

  it('shows the success summary when the sync completes', async () => {
    mockSyncStatus('success')
    server.use(
      http.post('*/mailboxes/mb-1/sync', () =>
        HttpResponse.json({
          status: 'success',
          total_emails_processed: 10,
          subscriptions_found: 2,
        }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(
      <SyncEmailsModal isOpen onClose={vi.fn()} mailbox={buildMailbox()} />,
    )
    await screen.findByText('Sync Emails')

    await user.click(screen.getByRole('button', { name: 'Start Sync' }))

    expect(
      await screen.findByText('Sync completed successfully!'),
    ).toBeInTheDocument()
    // The start controls are replaced once the sync finishes.
    expect(
      screen.queryByRole('button', { name: 'Start Sync' }),
    ).not.toBeInTheDocument()
  })

  it('sends the selected period in the sync request', async () => {
    mockSyncStatus('in_progress')
    let syncBody: Record<string, unknown> | null = null
    server.use(
      http.post('*/mailboxes/mb-1/sync', async ({ request }) => {
        syncBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ status: 'in_progress' })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(
      <SyncEmailsModal isOpen onClose={vi.fn()} mailbox={buildMailbox()} />,
    )
    await screen.findByText('Sync Emails')

    await user.selectOptions(screen.getByLabelText('Select Time Period'), '90days')
    await user.click(screen.getByRole('button', { name: 'Start Sync' }))

    await screen.findByText('In Progress')
    expect(syncBody).toMatchObject({
      force_full_sync: false,
      date_filter_override: '90days',
    })
  })

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <SyncEmailsModal isOpen onClose={onClose} mailbox={buildMailbox()} />,
    )
    await screen.findByText('Sync Emails')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
  })
})
