import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AdminInvitesPage } from './AdminInvitesPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Invite } from '@/api/admin'

function buildInvite(overrides: Partial<Invite> = {}): Invite {
  return {
    id: 'inv-1',
    token: 'tok-1',
    invite_url: 'https://app.example.com/invite/tok-1',
    invited_email: 'alice@example.com',
    note: 'VIP',
    is_used: false,
    expires_at: '2030-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function mockInvites(invites: Invite[]) {
  server.use(
    http.get('*/admin/invites', () => HttpResponse.json({ invites })),
  )
}

function row(email: string) {
  return within(screen.getByText(email).closest('tr') as HTMLElement)
}

describe('AdminInvitesPage', () => {
  it('shows a loading spinner while invites are being fetched', () => {
    server.use(
      http.get('*/admin/invites', async () => {
        await delay('infinite')
        return HttpResponse.json({ invites: [] })
      }),
    )

    renderWithProviders(<AdminInvitesPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the invites and the statistics', async () => {
    mockInvites([buildInvite()])

    renderWithProviders(<AdminInvitesPage />)

    expect(
      await screen.findByRole('heading', { name: 'Invite Management' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Total Invites')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(row('alice@example.com').getByText('Pending')).toBeInTheDocument()
  })

  it('shows an error toast when invites fail to load', async () => {
    server.use(
      http.get('*/admin/invites', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<AdminInvitesPage />)

    expect(await screen.findByText('Failed to load invites')).toBeInTheDocument()
  })

  it('shows the empty state when there are no invites', async () => {
    mockInvites([])

    renderWithProviders(<AdminInvitesPage />)

    expect(await screen.findByText('No invites created yet')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Create First Invite/ }),
    ).toBeInTheDocument()
  })

  it('creates an invite from the modal', async () => {
    mockInvites([])
    let createBody: Record<string, unknown> | null = null
    server.use(
      http.post('*/admin/invites', async ({ request }) => {
        createBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(buildInvite({ id: 'new' }))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminInvitesPage />)
    await screen.findByText('No invites created yet')

    await user.click(screen.getByRole('button', { name: 'Create Invite' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.type(
      dialog.getByRole('textbox', { name: 'Email (optional)' }),
      'bob@example.com',
    )
    await user.click(dialog.getByRole('button', { name: 'Create Invite' }))

    expect(await screen.findByText('Invite created')).toBeInTheDocument()
    expect(createBody).toMatchObject({ email: 'bob@example.com' })
  })

  it('revokes an invite after confirmation', async () => {
    let revokedId: string | null = null
    mockInvites([buildInvite()])
    server.use(
      http.delete('*/admin/invites/inv-1', () => {
        revokedId = 'inv-1'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminInvitesPage />)
    await screen.findByText('alice@example.com')

    await user.click(row('alice@example.com').getByRole('button', {
      name: 'Revoke invite',
    }))
    const dialog = within(await screen.findByRole('alertdialog'))
    await user.click(dialog.getByRole('button', { name: 'Revoke' }))

    expect(await screen.findByText('Invite revoked')).toBeInTheDocument()
    expect(revokedId).toBe('inv-1')
  })
})
