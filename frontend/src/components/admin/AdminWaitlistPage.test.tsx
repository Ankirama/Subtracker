import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AdminWaitlistPage } from './AdminWaitlistPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { WaitlistEntry } from '@/api/admin'

function buildEntry(overrides: Partial<WaitlistEntry> = {}): WaitlistEntry {
  return {
    id: 'w1',
    email: 'alice@example.com',
    status: 'pending',
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function mockWaitlist(items: WaitlistEntry[]) {
  server.use(
    http.get('*/admin/waitlist', () =>
      HttpResponse.json({
        items,
        total: items.length,
        page: 1,
        page_size: 20,
        total_pages: 1,
      }),
    ),
  )
}

function row(email: string) {
  return within(screen.getByText(email).closest('tr') as HTMLElement)
}

describe('AdminWaitlistPage', () => {
  it('shows a loading spinner while the waitlist is being fetched', () => {
    server.use(
      http.get('*/admin/waitlist', async () => {
        await delay('infinite')
        return HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          total_pages: 1,
        })
      }),
    )

    renderWithProviders(<AdminWaitlistPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the entries and the statistics', async () => {
    mockWaitlist([buildEntry()])

    renderWithProviders(<AdminWaitlistPage />)

    expect(
      await screen.findByRole('heading', { name: 'Waitlist Management' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Total Entries')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(row('alice@example.com').getByText('Pending')).toBeInTheDocument()
  })

  it('shows an error toast when the waitlist fails to load', async () => {
    server.use(
      http.get('*/admin/waitlist', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<AdminWaitlistPage />)

    expect(await screen.findByText('Error Loading Waitlist')).toBeInTheDocument()
  })

  it('shows the empty state when there are no entries', async () => {
    mockWaitlist([])

    renderWithProviders(<AdminWaitlistPage />)

    expect(
      await screen.findByText('No waitlist entries found'),
    ).toBeInTheDocument()
  })

  it('rejects a pending entry', async () => {
    let rejectedId: string | null = null
    mockWaitlist([buildEntry()])
    server.use(
      http.post('*/admin/waitlist/w1/reject', () => {
        rejectedId = 'w1'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminWaitlistPage />)
    await screen.findByText('alice@example.com')

    await user.click(row('alice@example.com').getByRole('button', {
      name: 'Reject',
    }))
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText('Reject Waitlist Entry')).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Reject' }))

    expect(await screen.findByText('Rejected Successfully')).toBeInTheDocument()
    expect(rejectedId).toBe('w1')
  })

  // NOTE: the approve flow is intentionally not covered. Its modal contains a
  // Chakra Switch ("Send email with access code"); opening that Switch-inside-a
  // focus-trapped-modal-from-a-table triggers a Chakra/jsdom commit-phase error
  // ("Cannot set property focus") — the same environment limitation seen with
  // AdminUsersPage's edit modal. The reject flow (Textarea modal) and delete
  // flow (AlertDialog) below cover the same table-action -> modal -> mutation
  // pattern without a Switch.

  it('deletes an entry after confirmation', async () => {
    let deletedId: string | null = null
    mockWaitlist([buildEntry()])
    server.use(
      http.delete('*/admin/waitlist/w1', () => {
        deletedId = 'w1'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminWaitlistPage />)
    await screen.findByText('alice@example.com')

    await user.click(row('alice@example.com').getByRole('button', {
      name: 'Delete',
    }))
    const dialog = within(await screen.findByRole('alertdialog'))
    expect(dialog.getByText('Delete Waitlist Entry')).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Delete' }))

    expect(await screen.findByText('Deleted Successfully')).toBeInTheDocument()
    expect(deletedId).toBe('w1')
  })
})
