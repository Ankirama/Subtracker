import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { NotificationListPage } from './NotificationListPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Notification, NotificationListResponse } from '@/api/notifications'

function buildNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'notif-1',
    user_id: 'user-1',
    type: 'TRIAL_ENDING',
    priority: 'medium',
    title: 'Spotify trial ending soon',
    message: 'Your Spotify trial ends in 3 days.',
    is_read: false,
    email_sent: false,
    created_at: '2026-05-01T10:00:00Z',
    ...overrides,
  }
}

function buildResponse(
  overrides: Partial<NotificationListResponse> = {},
): NotificationListResponse {
  const notifications = overrides.notifications ?? [
    buildNotification(),
    buildNotification({
      id: 'notif-2',
      title: 'Netflix renewal in 7 days',
      type: 'RENEWAL_REMINDER',
      is_read: true,
    }),
  ]
  const unread = notifications.filter((n) => !n.is_read).length
  return {
    notifications,
    total: notifications.length,
    unread_count: unread,
    page: 1,
    page_size: 20,
    has_more: false,
    ...overrides,
  }
}

describe('NotificationListPage', () => {
  it('shows a loading spinner while the notifications request is pending', () => {
    server.use(
      http.get('*/notifications', async () => {
        await delay('infinite')
        return HttpResponse.json(buildResponse())
      }),
    )

    renderWithProviders(<NotificationListPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows an error toast when the notifications request fails', async () => {
    server.use(
      http.get('*/notifications', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<NotificationListPage />)

    expect(
      await screen.findByText('Failed to load notifications'),
    ).toBeInTheDocument()
  })

  it('renders the notifications with the total and unread counts', async () => {
    server.use(
      http.get('*/notifications', () => HttpResponse.json(buildResponse())),
    )

    const { container } = renderWithProviders(<NotificationListPage />)

    // The header (incl. heading) renders before the query resolves, so wait for
    // the list content before asserting the counts.
    expect(
      await screen.findByText('Spotify trial ending soon'),
    ).toBeInTheDocument()
    expect(screen.getByText('Netflix renewal in 7 days')).toBeInTheDocument()
    // The count line interpolates values around a bullet across several text
    // nodes, so assert against the concatenated textContent.
    expect(container.textContent).toContain('2 total notifications')
    expect(container.textContent).toContain('1 unread')
  })

  it('requests unread-only notifications when that filter is selected', async () => {
    server.use(
      http.get('*/notifications', ({ request }) => {
        const url = new URL(request.url)
        if (url.searchParams.get('unread_only') === 'true') {
          return HttpResponse.json(
            buildResponse({ notifications: [buildNotification()] }),
          )
        }
        return HttpResponse.json(buildResponse())
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationListPage />)
    await screen.findByText('Netflix renewal in 7 days')

    // The read-state Select is the second combobox (type filter is first).
    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[1], 'unread')

    expect(await screen.findByText('Spotify trial ending soon')).toBeInTheDocument()
    expect(
      screen.queryByText('Netflix renewal in 7 days'),
    ).not.toBeInTheDocument()
  })

  it('marks all notifications as read', async () => {
    server.use(
      http.get('*/notifications', () => HttpResponse.json(buildResponse())),
      http.post('*/notifications/mark-all-read', () =>
        HttpResponse.json({ success: true, marked_read: 1 }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationListPage />)
    await user.click(await screen.findByRole('button', { name: /mark all read/i }))

    expect(
      await screen.findByText('All notifications marked as read'),
    ).toBeInTheDocument()
  })

  it('deletes a notification', async () => {
    let deleteCalledFor: string | null = null
    server.use(
      http.get('*/notifications', () => HttpResponse.json(buildResponse())),
      http.delete('*/notifications/notif-1', () => {
        deleteCalledFor = 'notif-1'
        return HttpResponse.json({ success: true })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationListPage />)
    const card = (await screen.findByText('Spotify trial ending soon')).closest(
      '.chakra-card',
    ) as HTMLElement
    await user.click(
      within(card).getByRole('button', { name: 'Delete notification' }),
    )

    expect(await screen.findByText('Notification deleted')).toBeInTheDocument()
    expect(deleteCalledFor).toBe('notif-1')
  })

  it('shows the empty state when there are no notifications', async () => {
    server.use(
      http.get('*/notifications', () =>
        HttpResponse.json(
          buildResponse({ notifications: [], total: 0, unread_count: 0 }),
        ),
      ),
    )

    renderWithProviders(<NotificationListPage />)

    expect(await screen.findByText('No notifications found')).toBeInTheDocument()
    expect(screen.getByText('You are all caught up')).toBeInTheDocument()
  })

  it('paginates to the next page of notifications', async () => {
    server.use(
      http.get('*/notifications', ({ request }) => {
        const url = new URL(request.url)
        const page = Number(url.searchParams.get('page') ?? '1')
        return HttpResponse.json(
          buildResponse({
            notifications: [
              buildNotification({
                id: `p${page}`,
                title: `Notification on page ${page}`,
              }),
            ],
            total: 40,
            page,
          }),
        )
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationListPage />)
    await screen.findByText('Notification on page 1')
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Next page' }))

    expect(await screen.findByText('Notification on page 2')).toBeInTheDocument()
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
  })
})
