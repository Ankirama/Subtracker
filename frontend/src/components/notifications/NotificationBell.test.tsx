import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { NotificationBell } from './NotificationBell'
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

function buildNotificationsResponse(
  overrides: Partial<NotificationListResponse> = {},
): NotificationListResponse {
  const notifications = overrides.notifications ?? [
    buildNotification(),
    buildNotification({ id: 'notif-2', title: 'Netflix renewal in 7 days' }),
  ]
  const unread = notifications.filter((n) => !n.is_read).length
  return {
    notifications,
    total: notifications.length,
    unread_count: unread,
    page: 1,
    page_size: 10,
    has_more: false,
    ...overrides,
  }
}

describe('NotificationBell', () => {
  it('renders the unread count badge after the initial fetch', async () => {
    server.use(
      http.get('*/notifications/unread-count', () =>
        HttpResponse.json({ unread_count: 3 }),
      ),
    )

    renderWithProviders(<NotificationBell />)

    const trigger = await screen.findByRole('button', { name: 'Notifications' })
    expect(within(trigger.parentElement!).getByText('3')).toBeInTheDocument()
  })

  it('loads and renders notifications when the popover is opened', async () => {
    server.use(
      http.get('*/notifications/unread-count', () =>
        HttpResponse.json({ unread_count: 2 }),
      ),
      http.get('*/notifications', () =>
        HttpResponse.json(buildNotificationsResponse()),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)
    await user.click(await screen.findByRole('button', { name: 'Notifications' }))

    expect(await screen.findByText('Spotify trial ending soon')).toBeInTheDocument()
    expect(screen.getByText('Netflix renewal in 7 days')).toBeInTheDocument()
  })

  it('shows an error toast when the notifications fetch fails', async () => {
    server.use(
      http.get('*/notifications/unread-count', () =>
        HttpResponse.json({ unread_count: 1 }),
      ),
      http.get('*/notifications', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)
    await user.click(await screen.findByRole('button', { name: 'Notifications' }))

    expect(
      await screen.findByText('Failed to load notifications'),
    ).toBeInTheDocument()
  })

  it('decrements the badge after marking one notification as read', async () => {
    server.use(
      http.get('*/notifications/unread-count', () =>
        HttpResponse.json({ unread_count: 2 }),
      ),
      http.get('*/notifications', () =>
        HttpResponse.json(buildNotificationsResponse()),
      ),
      http.post('*/notifications/mark-read', () =>
        HttpResponse.json({ success: true, marked_read: 1 }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)
    const trigger = await screen.findByRole('button', { name: 'Notifications' })
    await user.click(trigger)
    await user.click(await screen.findByText('Spotify trial ending soon'))

    expect(
      await within(trigger.parentElement!).findByText('1'),
    ).toBeInTheDocument()
  })

  it('hides the badge after "Mark all read" succeeds', async () => {
    server.use(
      http.get('*/notifications/unread-count', () =>
        HttpResponse.json({ unread_count: 2 }),
      ),
      http.get('*/notifications', () =>
        HttpResponse.json(buildNotificationsResponse()),
      ),
      http.post('*/notifications/mark-all-read', () =>
        HttpResponse.json({ success: true, marked_read: 2 }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)
    const trigger = await screen.findByRole('button', { name: 'Notifications' })
    await user.click(trigger)
    await user.click(await screen.findByRole('button', { name: /mark all read/i }))

    // Wait for the success toast to confirm the async path settled, then
    // assert the badge container no longer contains the prior count.
    await screen.findByText('All notifications marked as read')
    expect(within(trigger.parentElement!).queryByText('2')).not.toBeInTheDocument()
  })

  it('removes a notification and decrements the badge after deleting it', async () => {
    server.use(
      http.get('*/notifications/unread-count', () =>
        HttpResponse.json({ unread_count: 2 }),
      ),
      http.get('*/notifications', () =>
        HttpResponse.json(buildNotificationsResponse()),
      ),
      http.delete('*/notifications/notif-1', () =>
        HttpResponse.json({ success: true }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)
    const trigger = await screen.findByRole('button', { name: 'Notifications' })
    await user.click(trigger)
    await screen.findByText('Spotify trial ending soon')

    // The first delete button belongs to the first (Spotify) notification.
    const [deleteButton] = screen.getAllByRole('button', {
      name: 'Delete notification',
    })
    await user.click(deleteButton)

    await screen.findByText('Notification deleted')
    expect(
      screen.queryByText('Spotify trial ending soon'),
    ).not.toBeInTheDocument()
    expect(
      await within(trigger.parentElement!).findByText('1'),
    ).toBeInTheDocument()
  })

  it('shows the empty state when there are no notifications', async () => {
    server.use(
      http.get('*/notifications/unread-count', () =>
        HttpResponse.json({ unread_count: 0 }),
      ),
      http.get('*/notifications', () =>
        HttpResponse.json(buildNotificationsResponse({ notifications: [] })),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationBell />)
    await user.click(await screen.findByRole('button', { name: 'Notifications' }))

    expect(await screen.findByText('No notifications')).toBeInTheDocument()
  })
})
