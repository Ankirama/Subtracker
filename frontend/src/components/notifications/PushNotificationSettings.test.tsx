import { describe, it, expect, afterEach, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { PushNotificationSettings } from './PushNotificationSettings'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

describe('PushNotificationSettings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the unsupported warning when push is not available', () => {
    // jsdom exposes neither serviceWorker nor PushManager by default.
    renderWithProviders(<PushNotificationSettings />, { withAuth: false })

    expect(
      screen.getByText(/Push notifications are not supported in your browser/),
    ).toBeInTheDocument()
  })

  it('renders the toggle when push is supported', async () => {
    vi.stubGlobal('PushManager', class {})
    vi.stubGlobal('Notification', { permission: 'default' })
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: {
        ready: Promise.resolve({
          pushManager: { getSubscription: async () => null },
        }),
      },
    })
    server.use(
      http.get('*/push/vapid-public-key', () =>
        HttpResponse.json({ publicKey: 'test-key' }),
      ),
    )

    renderWithProviders(<PushNotificationSettings />, { withAuth: false })

    expect(
      await screen.findByText('Enable Push Notifications'),
    ).toBeInTheDocument()
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })
})
