import { describe, it, expect } from 'vitest'
import { screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AdminIPWhitelistPage } from './AdminIPWhitelistPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { IPWhitelistEntry } from '@/api/admin'

function buildEntry(overrides: Partial<IPWhitelistEntry> = {}): IPWhitelistEntry {
  return {
    ip_address: '10.0.0.1',
    description: 'Office',
    added_by_user_id: 'user-1',
    added_at: '2026-01-01T00:00:00Z',
    last_seen: '2026-02-01T00:00:00Z',
    access_count: 42,
    ...overrides,
  }
}

function entriesResponse(items: IPWhitelistEntry[], totalPages = 1, total = items.length) {
  return { items, total, page: 1, page_size: 20, total_pages: totalPages }
}

function mockList(items: IPWhitelistEntry[], opts: { status?: number } = {}) {
  server.use(
    http.get('*/admin/security/ip-whitelist', () =>
      opts.status && opts.status !== 200
        ? HttpResponse.json({ detail: 'boom' }, { status: opts.status })
        : HttpResponse.json(entriesResponse(items)),
    ),
  )
}

function row(text: string) {
  return within(screen.getByText(text).closest('tr') as HTMLElement)
}

describe('AdminIPWhitelistPage', () => {
  it('shows a loading spinner while entries are being fetched', () => {
    server.use(
      http.get('*/admin/security/ip-whitelist', async () => {
        await delay('infinite')
        return HttpResponse.json(entriesResponse([]))
      }),
    )

    renderWithProviders(<AdminIPWhitelistPage />)

    // Both the table spinner and the Refresh button's isLoading spinner are
    // labelled "Loading...", so assert at least one is present.
    expect(screen.getAllByText('Loading...').length).toBeGreaterThan(0)
  })

  it('renders the whitelisted entries', async () => {
    mockList([buildEntry()])

    renderWithProviders(<AdminIPWhitelistPage />)

    expect(
      await screen.findByRole('heading', { name: 'IP Whitelist Management' }),
    ).toBeInTheDocument()
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument()
    const entryRow = row('10.0.0.1')
    expect(entryRow.getByText('Office')).toBeInTheDocument()
    expect(entryRow.getByText('42')).toBeInTheDocument()
  })

  it('shows an error toast when entries fail to load', async () => {
    mockList([], { status: 500 })

    renderWithProviders(<AdminIPWhitelistPage />)

    expect(
      await screen.findByText('Error Loading IP Whitelist'),
    ).toBeInTheDocument()
  })

  it('shows the empty state when there are no entries', async () => {
    mockList([])

    renderWithProviders(<AdminIPWhitelistPage />)

    expect(
      await screen.findByText('No whitelisted IP addresses'),
    ).toBeInTheDocument()
  })

  it('adds a new IP to the whitelist', async () => {
    let postedBody: unknown = null
    mockList([])
    server.use(
      http.post('*/admin/security/ip-whitelist', async ({ request }) => {
        postedBody = await request.json()
        return HttpResponse.json(buildEntry({ ip_address: '192.168.1.5' }), {
          status: 201,
        })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminIPWhitelistPage />)
    await screen.findByText('No whitelisted IP addresses')

    await user.click(screen.getByRole('button', { name: 'Add IP' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.type(
      dialog.getByPlaceholderText('192.168.1.1 or 2001:db8::1'),
      '192.168.1.5',
    )
    await user.type(
      dialog.getByPlaceholderText('e.g., Admin office IP, VPN gateway'),
      'VPN gateway',
    )
    await user.click(dialog.getByRole('button', { name: 'Add to Whitelist' }))

    expect(await screen.findByText('IP Added to Whitelist')).toBeInTheDocument()
    expect(postedBody).toEqual({
      ip_address: '192.168.1.5',
      description: 'VPN gateway',
    })
  })

  it('warns when adding an IP without an address', async () => {
    mockList([])
    const user = userEvent.setup()

    renderWithProviders(<AdminIPWhitelistPage />)
    await screen.findByText('No whitelisted IP addresses')

    await user.click(screen.getByRole('button', { name: 'Add IP' }))
    const dialog = within(await screen.findByRole('dialog'))
    // No POST handler is registered: if the request fired, MSW would error.
    await user.click(dialog.getByRole('button', { name: 'Add to Whitelist' }))

    expect(await screen.findByText('Validation Error')).toBeInTheDocument()
  })

  it('edits the description of an entry', async () => {
    let patchedBody: unknown = null
    mockList([buildEntry()])
    server.use(
      http.patch('*/admin/security/ip-whitelist/10.0.0.1', async ({ request }) => {
        patchedBody = await request.json()
        return HttpResponse.json(buildEntry({ description: 'Updated office' }))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminIPWhitelistPage />)
    await screen.findByText('10.0.0.1')

    await user.click(row('10.0.0.1').getByRole('button', { name: 'Edit' }))
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText('Edit IP Whitelist Entry')).toBeInTheDocument()
    const description = dialog.getByLabelText('Description')
    await user.clear(description)
    await user.type(description, 'Updated office')
    await user.click(dialog.getByRole('button', { name: 'Update' }))

    expect(
      await screen.findByText('Whitelist Entry Updated'),
    ).toBeInTheDocument()
    expect(patchedBody).toEqual({ description: 'Updated office' })
  })

  it('removes an entry after confirmation', async () => {
    let deletedIp: string | null = null
    mockList([buildEntry()])
    server.use(
      http.delete('*/admin/security/ip-whitelist/10.0.0.1', () => {
        deletedIp = '10.0.0.1'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminIPWhitelistPage />)
    await screen.findByText('10.0.0.1')

    await user.click(row('10.0.0.1').getByRole('button', { name: 'Delete' }))
    const dialog = within(await screen.findByRole('alertdialog'))
    expect(dialog.getByText('Remove IP from Whitelist')).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Remove' }))

    expect(
      await screen.findByText('IP Removed from Whitelist'),
    ).toBeInTheDocument()
    expect(deletedIp).toBe('10.0.0.1')
  })

  it('paginates to the next page of entries', async () => {
    server.use(
      http.get('*/admin/security/ip-whitelist', ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get('page') ?? '1')
        return HttpResponse.json(
          entriesResponse([buildEntry({ ip_address: `10.0.0.${page}` })], 2, 40),
        )
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminIPWhitelistPage />)
    await screen.findByText('10.0.0.1')

    await user.click(screen.getByRole('button', { name: 'Next page' }))

    expect(await screen.findByText('10.0.0.2')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByText(/Page 2 of 2/)).toBeInTheDocument(),
    )
  })
})
