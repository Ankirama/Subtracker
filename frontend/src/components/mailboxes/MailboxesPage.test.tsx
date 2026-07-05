import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { MailboxesPage } from './MailboxesPage'
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
    last_sync_status: 'success',
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

function mockList(mailboxes: Mailbox[]) {
  server.use(http.get('*/mailboxes', () => HttpResponse.json(mailboxes)))
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('MailboxesPage', () => {
  it('shows a loading spinner while mailboxes are being fetched', () => {
    server.use(
      http.get('*/mailboxes', async () => {
        await delay('infinite')
        return HttpResponse.json([])
      }),
    )

    renderWithProviders(<MailboxesPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows an error alert when the mailboxes request fails', async () => {
    server.use(
      http.get('*/mailboxes', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<MailboxesPage />)

    expect(
      await screen.findByText('Failed to load mailboxes. Please try again.'),
    ).toBeInTheDocument()
  })

  it('shows the empty state when there are no mailboxes', async () => {
    mockList([])

    renderWithProviders(<MailboxesPage />)

    expect(
      await screen.findByText('No mailboxes connected yet'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Add Your First Mailbox/ }),
    ).toBeInTheDocument()
  })

  it('renders a connected mailbox card', async () => {
    mockList([buildMailbox()])

    renderWithProviders(<MailboxesPage />)

    expect(
      await screen.findByRole('heading', { name: 'Personal Gmail' }),
    ).toBeInTheDocument()
    expect(screen.getByText('me@example.com')).toBeInTheDocument()
    expect(screen.getByText(/1 connected mailbox/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sync Emails' })).toBeInTheDocument()
  })

  it('deletes a mailbox after confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    let deletedId: string | null = null
    mockList([buildMailbox()])
    server.use(
      http.delete('*/mailboxes/mb-1', () => {
        deletedId = 'mb-1'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<MailboxesPage />)
    const heading = await screen.findByRole('heading', { name: 'Personal Gmail' })
    const card = heading.closest('.chakra-card') as HTMLElement

    await user.click(within(card).getByRole('button', { name: 'Delete' }))

    expect(confirmSpy).toHaveBeenCalled()
    expect(await screen.findByText('Mailbox deleted')).toBeInTheDocument()
    expect(deletedId).toBe('mb-1')
  })

  it('shows a success toast after a Gmail OAuth callback', async () => {
    mockList([])

    renderWithProviders(<MailboxesPage />, {
      route: '/mailboxes?success=gmail_connected',
    })

    expect(await screen.findByText('Gmail Connected')).toBeInTheDocument()
  })

  it('shows an error toast when the Gmail OAuth callback fails', async () => {
    mockList([])

    renderWithProviders(<MailboxesPage />, {
      route: '/mailboxes?error=access_denied',
    })

    expect(await screen.findByText('Gmail Connection Failed')).toBeInTheDocument()
  })
})
