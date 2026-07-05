import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { AddMailboxModal } from './AddMailboxModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import { mailboxesAPI } from '@/api/mailboxes'
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

afterEach(() => {
  vi.restoreAllMocks()
})

// Fill in the JMAP credential fields (shared by the test/create flows).
async function fillJmapForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole('textbox', { name: 'Mailbox Name' }), 'Work')
  await user.type(
    screen.getByRole('textbox', { name: 'Email Address' }),
    'me@example.com',
  )
  await user.type(
    screen.getByRole('textbox', { name: 'JMAP Server URL' }),
    'https://jmap.example.com',
  )
  await user.type(
    screen.getByRole('textbox', { name: 'Username' }),
    'me@example.com',
  )
  await user.type(screen.getByPlaceholderText('••••••••'), 'secret')
}

describe('AddMailboxModal', () => {
  it('renders the provider selection screen for a new mailbox', async () => {
    renderWithProviders(
      <AddMailboxModal isOpen onClose={vi.fn()} mailbox={null} />,
    )

    expect(await screen.findByText('Add Mailbox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Gmail/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /JMAP/ })).toBeInTheDocument()
  })

  it('reveals the JMAP configuration form when JMAP is selected', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <AddMailboxModal isOpen onClose={vi.fn()} mailbox={null} />,
    )
    await screen.findByText('Add Mailbox')

    await user.click(screen.getByRole('button', { name: /JMAP/ }))

    expect(
      screen.getByRole('textbox', { name: 'JMAP Server URL' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Test Connection' }),
    ).toBeInTheDocument()
  })

  it('shows an error toast when starting the Gmail connection fails', async () => {
    vi.spyOn(mailboxesAPI, 'getGoogleAuthUrl').mockRejectedValue({
      response: { data: { detail: 'Google OAuth is not configured' } },
    })
    const user = userEvent.setup()
    renderWithProviders(
      <AddMailboxModal isOpen onClose={vi.fn()} mailbox={null} />,
    )
    await screen.findByText('Add Mailbox')

    await user.click(screen.getByRole('button', { name: /Gmail/ }))

    expect(
      await screen.findByText('Failed to connect Gmail'),
    ).toBeInTheDocument()
  })

  it('warns when testing the connection with missing credentials', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <AddMailboxModal isOpen onClose={vi.fn()} mailbox={null} />,
    )
    await screen.findByText('Add Mailbox')
    await user.click(screen.getByRole('button', { name: /JMAP/ }))

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(await screen.findByText('Missing credentials')).toBeInTheDocument()
  })

  it('tests the JMAP connection successfully', async () => {
    server.use(
      http.post('*/mailboxes/test', () =>
        HttpResponse.json({ success: true, message: 'Connection successful!' }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(
      <AddMailboxModal isOpen onClose={vi.fn()} mailbox={null} />,
    )
    await screen.findByText('Add Mailbox')
    await user.click(screen.getByRole('button', { name: /JMAP/ }))
    await fillJmapForm(user)

    await user.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(
      await screen.findByText('Connection test successful'),
    ).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('creates a JMAP mailbox after a successful connection test', async () => {
    const onClose = vi.fn()
    let createBody: Record<string, unknown> | null = null
    server.use(
      http.post('*/mailboxes/test', () =>
        HttpResponse.json({ success: true, message: 'ok' }),
      ),
      http.post('*/mailboxes', async ({ request }) => {
        createBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(buildMailbox({ provider_type: 'jmap' }))
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(
      <AddMailboxModal isOpen onClose={onClose} mailbox={null} />,
    )
    await screen.findByText('Add Mailbox')
    await user.click(screen.getByRole('button', { name: /JMAP/ }))
    await fillJmapForm(user)
    await user.click(screen.getByRole('button', { name: 'Test Connection' }))
    await screen.findByText('Connected')

    await user.click(screen.getByRole('button', { name: 'Add Mailbox' }))

    expect(await screen.findByText('Mailbox added')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalled()
    expect(createBody).toMatchObject({
      provider_type: 'jmap',
      email_address: 'me@example.com',
    })
  })

  it('updates a Gmail mailbox display name', async () => {
    const onClose = vi.fn()
    let updatedId: string | null = null
    let updatedBody: Record<string, unknown> | null = null
    server.use(
      http.put('*/mailboxes/mb-1', async ({ request }) => {
        updatedId = 'mb-1'
        updatedBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(buildMailbox())
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(
      <AddMailboxModal isOpen onClose={onClose} mailbox={buildMailbox()} />,
    )
    await screen.findByText('Edit Mailbox')

    const nameInput = screen.getByRole('textbox', { name: 'Display Name' })
    await user.clear(nameInput)
    await user.type(nameInput, 'My Gmail')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText('Mailbox updated')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalled()
    expect(updatedId).toBe('mb-1')
    expect(updatedBody).toMatchObject({ display_name: 'My Gmail' })
  })

  it('calls onClose when Cancel is clicked in the edit form', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(
      <AddMailboxModal isOpen onClose={onClose} mailbox={buildMailbox()} />,
    )
    await screen.findByText('Edit Mailbox')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
  })
})
