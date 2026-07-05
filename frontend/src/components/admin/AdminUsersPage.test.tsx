import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AdminUsersPage } from './AdminUsersPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { User, UserDetail, UserStats } from '@/api/admin'

const defaultStats: UserStats = {
  total_users: 2,
  active_users: 2,
  inactive_users: 0,
  admin_users: 0,
  new_users_30d: 1,
}

const alice: User = {
  id: 'alice-id',
  email: 'alice@example.com',
  is_active: true,
  is_admin: false,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
}

const bob: User = {
  id: 'bob-id',
  email: 'bob@example.com',
  is_active: true,
  is_admin: false,
  email_verified: false,
  created_at: '2026-02-01T00:00:00Z',
  updated_at: '2026-02-02T00:00:00Z',
}

const aliceDetail: UserDetail = {
  ...alice,
  settings: {},
  subscription_count: 3,
  mailbox_count: 1,
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handlers(opts: any = {}) {
  const {
    users = [alice, bob],
    stats = defaultStats,
    listStatus = 200,
    extra = [],
  } = opts
  return [
    // Register the stats handler before the ":id" handler so /admin/users/stats
    // is not swallowed by the parameterised route.
    http.get('*/admin/users/stats', () => HttpResponse.json(stats)),
    ...extra,
    http.get('*/admin/users', () =>
      listStatus === 200
        ? HttpResponse.json({
            users,
            total: users.length,
            page: 1,
            page_size: 20,
            total_pages: 1,
          })
        : HttpResponse.json({ detail: 'boom' }, { status: listStatus }),
    ),
  ]
}

// Both the desktop table and the action buttons repeat per row; scope to a row.
function row(email: string) {
  const cell = screen.getByText(email)
  return within(cell.closest('tr') as HTMLElement)
}

describe('AdminUsersPage', () => {
  it('shows a loading spinner while users are being fetched', () => {
    server.use(
      http.get('*/admin/users/stats', () => HttpResponse.json(defaultStats)),
      http.get('*/admin/users', async () => {
        await delay('infinite')
        return HttpResponse.json({
          users: [],
          total: 0,
          page: 1,
          page_size: 20,
          total_pages: 1,
        })
      }),
    )

    renderWithProviders(<AdminUsersPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the user rows and the statistics cards', async () => {
    server.use(...handlers())

    renderWithProviders(<AdminUsersPage />)

    expect(
      await screen.findByText('alice@example.com'),
    ).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    // Statistics cards.
    expect(screen.getByText('Total Users')).toBeInTheDocument()
    expect(screen.getByText('Active Users')).toBeInTheDocument()
    expect(screen.getByText('Admin Users')).toBeInTheDocument()
    // Bob is unverified.
    expect(row('bob@example.com').getByText('Unverified')).toBeInTheDocument()
  })

  it('shows an error toast when the user list fails to load', async () => {
    server.use(...handlers({ listStatus: 500 }))

    renderWithProviders(<AdminUsersPage />)

    expect(await screen.findByText('Error Loading Users')).toBeInTheDocument()
  })

  it('shows the empty state when there are no users', async () => {
    server.use(...handlers({ users: [] }))

    renderWithProviders(<AdminUsersPage />)

    expect(await screen.findByText('No users found')).toBeInTheDocument()
  })

  it('opens the details modal for a user', async () => {
    server.use(
      ...handlers({
        extra: [
          http.get('*/admin/users/:id', () => HttpResponse.json(aliceDetail)),
        ],
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminUsersPage />)
    await screen.findByText('alice@example.com')

    await user.click(row('alice@example.com').getByRole('button', {
      name: 'View details',
    }))

    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText('User Details')).toBeInTheDocument()
    expect(dialog.getByText('Subscriptions')).toBeInTheDocument()
    expect(dialog.getByText('3')).toBeInTheDocument() // subscription_count
  })

  // NOTE: the edit flow (opening the Switch-containing Edit modal and saving) is
  // intentionally not covered here. Under jsdom, opening that focus-trapped modal
  // triggers a Chakra/jsdom commit-phase error ("Cannot set property focus") that
  // is an environment limitation, not a product bug. The same modal-with-Switch +
  // save pattern is already covered by the SubscriptionModal and BudgetModal
  // suites, which render their modals directly.

  it('verifies an unverified user email', async () => {
    let verifiedId: string | null = null
    server.use(
      ...handlers({
        extra: [
          http.post('*/admin/users/:id/verify', ({ params }) => {
            verifiedId = params.id as string
            return HttpResponse.json({ success: true, message: 'ok' })
          }),
        ],
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminUsersPage />)
    await screen.findByText('bob@example.com')

    await user.click(row('bob@example.com').getByRole('button', {
      name: 'Verify email',
    }))

    expect(await screen.findByText('Email Verified')).toBeInTheDocument()
    expect(verifiedId).toBe('bob-id')
  })

  it('deactivates a user after confirmation', async () => {
    let deletedId: string | null = null
    server.use(
      ...handlers({
        extra: [
          http.delete('*/admin/users/:id', ({ params }) => {
            deletedId = params.id as string
            return new HttpResponse(null, { status: 204 })
          }),
        ],
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminUsersPage />)
    await screen.findByText('alice@example.com')

    await user.click(row('alice@example.com').getByRole('button', {
      name: 'Delete user',
    }))

    const dialog = within(await screen.findByRole('alertdialog'))
    expect(dialog.getByText('Deactivate User')).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Deactivate' }))

    expect(await screen.findByText('User Deactivated')).toBeInTheDocument()
    expect(deletedId).toBe('alice-id')
  })
})
