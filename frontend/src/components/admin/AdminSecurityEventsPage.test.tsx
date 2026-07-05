import { describe, it, expect } from 'vitest'
import { screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AdminSecurityEventsPage } from './AdminSecurityEventsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { SecurityEvent, SecurityStats } from '@/api/admin'

function buildEvent(overrides: Partial<SecurityEvent> = {}): SecurityEvent {
  return {
    id: 'evt-1',
    event_type: 'failed_login',
    ip_address: '1.2.3.4',
    user_agent: 'Mozilla/5.0',
    severity: 'high',
    is_resolved: false,
    details: { attempts: 5 },
    created_at: '2026-05-01T10:00:00Z',
    ...overrides,
  }
}

const defaultStats: SecurityStats = {
  total_events: 10,
  unresolved_events: 4,
  events_24h: 2,
  critical_unresolved: 1,
  by_severity: { low: 1, medium: 1, high: 1, critical: 1 },
}

function mockSecurityBase() {
  server.use(
    http.get('*/admin/security/stats', () => HttpResponse.json(defaultStats)),
    // Filter option values kept distinct from the row event_type strings so
    // getByText('failed_login') resolves to the table cell, not an <option>.
    http.get('*/admin/security/event-types', () =>
      HttpResponse.json({ event_types: ['auth_failure', 'anomaly'] }),
    ),
  )
}

function eventsResponse(items: SecurityEvent[], totalPages = 1, total = items.length) {
  return { items, total, page: 1, page_size: 20, total_pages: totalPages }
}

function row(text: string) {
  return within(screen.getByText(text).closest('tr') as HTMLElement)
}

describe('AdminSecurityEventsPage', () => {
  it('shows a loading spinner while events are being fetched', () => {
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', async () => {
        await delay('infinite')
        return HttpResponse.json(eventsResponse([]))
      }),
    )

    renderWithProviders(<AdminSecurityEventsPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the events and the statistics', async () => {
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', () =>
        HttpResponse.json(eventsResponse([buildEvent()])),
      ),
    )

    renderWithProviders(<AdminSecurityEventsPage />)

    expect(
      await screen.findByRole('heading', { name: 'Security Events' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Total Events')).toBeInTheDocument()
    expect(screen.getByText('failed_login')).toBeInTheDocument()
    const eventRow = row('failed_login')
    expect(eventRow.getByText('HIGH')).toBeInTheDocument()
    expect(eventRow.getByText('Unresolved')).toBeInTheDocument()
  })

  it('shows an error toast when events fail to load', async () => {
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<AdminSecurityEventsPage />)

    expect(
      await screen.findByText('Error Loading Security Events'),
    ).toBeInTheDocument()
  })

  it('shows the empty state when there are no events', async () => {
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', () => HttpResponse.json(eventsResponse([]))),
    )

    renderWithProviders(<AdminSecurityEventsPage />)

    expect(
      await screen.findByText('No security events found'),
    ).toBeInTheDocument()
  })

  it('filters the events by severity', async () => {
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', ({ request }) => {
        const severity = new URL(request.url).searchParams.get('severity')
        if (severity === 'critical') {
          return HttpResponse.json(
            eventsResponse([
              buildEvent({
                id: 'evt-2',
                event_type: 'sql_injection',
                severity: 'critical',
              }),
            ]),
          )
        }
        return HttpResponse.json(eventsResponse([buildEvent()]))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminSecurityEventsPage />)
    await screen.findByText('failed_login')

    await user.selectOptions(screen.getByLabelText('Severity'), 'critical')

    expect(await screen.findByText('sql_injection')).toBeInTheDocument()
    expect(screen.queryByText('failed_login')).not.toBeInTheDocument()
  })

  it('opens the event details modal', async () => {
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', () =>
        HttpResponse.json(eventsResponse([buildEvent()])),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminSecurityEventsPage />)
    await screen.findByText('failed_login')

    await user.click(row('failed_login').getByRole('button', {
      name: 'View details',
    }))

    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText('Security Event Details')).toBeInTheDocument()
    expect(dialog.getByText('1.2.3.4')).toBeInTheDocument()
    expect(dialog.getByText('Mozilla/5.0')).toBeInTheDocument()
  })

  it('toggles an event as resolved', async () => {
    let patchedBody: unknown = null
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', () =>
        HttpResponse.json(eventsResponse([buildEvent()])),
      ),
      http.patch('*/admin/security/evt-1', async ({ request }) => {
        patchedBody = await request.json()
        return HttpResponse.json(buildEvent({ is_resolved: true }))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminSecurityEventsPage />)
    await screen.findByText('failed_login')

    await user.click(row('failed_login').getByRole('button', {
      name: 'Toggle resolved',
    }))

    expect(
      await screen.findByText('Event Marked as Resolved'),
    ).toBeInTheDocument()
    expect(patchedBody).toEqual({ is_resolved: true })
  })

  it('deletes an event after confirmation', async () => {
    let deletedId: string | null = null
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', () =>
        HttpResponse.json(eventsResponse([buildEvent()])),
      ),
      http.delete('*/admin/security/evt-1', () => {
        deletedId = 'evt-1'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminSecurityEventsPage />)
    await screen.findByText('failed_login')

    await user.click(row('failed_login').getByRole('button', {
      name: 'Delete event',
    }))
    const dialog = within(await screen.findByRole('alertdialog'))
    expect(dialog.getByText('Delete Security Event')).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Delete' }))

    expect(await screen.findByText('Event Deleted')).toBeInTheDocument()
    expect(deletedId).toBe('evt-1')
  })

  it('paginates to the next page of events', async () => {
    mockSecurityBase()
    server.use(
      http.get('*/admin/security', ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get('page') ?? '1')
        return HttpResponse.json(
          eventsResponse(
            [buildEvent({ id: `p${page}`, event_type: `event_page_${page}` })],
            2,
            40,
          ),
        )
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminSecurityEventsPage />)
    await screen.findByText('event_page_1')

    await user.click(screen.getByRole('button', { name: 'Next page' }))

    expect(await screen.findByText('event_page_2')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByText(/Showing page 2 of 2/)).toBeInTheDocument(),
    )
  })
})
