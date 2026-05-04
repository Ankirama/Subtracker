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
})
