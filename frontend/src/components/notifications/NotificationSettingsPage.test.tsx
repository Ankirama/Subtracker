import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { NotificationSettingsPage } from './NotificationSettingsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { NotificationPreference, NotificationType } from '@/api/notifications'

function pref(
  type: NotificationType,
  overrides: Partial<NotificationPreference> = {},
): NotificationPreference {
  return {
    id: type,
    user_id: 'u1',
    notification_type: type,
    enabled: true,
    in_app_enabled: true,
    email_enabled: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function mockPreferences(preferences: NotificationPreference[]) {
  server.use(
    http.get('*/notifications/preferences', () =>
      HttpResponse.json({ preferences }),
    ),
  )
}

// PushNotificationSettings renders its "not supported" branch in jsdom (no
// serviceWorker/PushManager), so it needs no push endpoint handlers here.

describe('NotificationSettingsPage', () => {
  it('shows a spinner while preferences load', () => {
    server.use(
      http.get('*/notifications/preferences', async () => {
        await delay('infinite')
        return HttpResponse.json({ preferences: [] })
      }),
    )

    const { container } = renderWithProviders(<NotificationSettingsPage />, {
      withAuth: false,
    })

    expect(container.querySelector('.chakra-spinner')).toBeInTheDocument()
  })

  it('renders a card per configured notification type', async () => {
    mockPreferences([
      pref('RENEWAL_REMINDER', { days_before_renewal: 3 }),
      pref('WEEKLY_SUMMARY', { summary_day_of_week: 0 }),
      pref('TRIAL_ENDING', { enabled: false }),
    ])

    renderWithProviders(<NotificationSettingsPage />, { withAuth: false })

    expect(await screen.findByText('Renewal Reminders')).toBeInTheDocument()
    expect(screen.getByText('Weekly Summary')).toBeInTheDocument()
    expect(screen.getByText('Trial Ending Reminders')).toBeInTheDocument()
  })

  it('shows an error toast when preferences fail to load', async () => {
    server.use(
      http.get('*/notifications/preferences', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<NotificationSettingsPage />, { withAuth: false })

    expect(
      await screen.findByText('Failed to load notification preferences'),
    ).toBeInTheDocument()
  })

  it('updates a preference when a type-specific setting changes', async () => {
    let putBody: unknown = null
    let putType: string | null = null
    mockPreferences([pref('WEEKLY_SUMMARY', { summary_day_of_week: 0 })])
    server.use(
      http.put('*/notifications/preferences/:type', async ({ request, params }) => {
        putType = params.type as string
        putBody = await request.json()
        return HttpResponse.json(pref('WEEKLY_SUMMARY', { summary_day_of_week: 2 }))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<NotificationSettingsPage />, { withAuth: false })
    await screen.findByText('Weekly Summary')

    await user.selectOptions(
      screen.getByLabelText('Day to send summary'),
      'Wednesday',
    )

    expect(await screen.findByText('Preference updated')).toBeInTheDocument()
    expect(putType).toBe('WEEKLY_SUMMARY')
    expect(putBody).toEqual({ summary_day_of_week: 2 })
  })
})
