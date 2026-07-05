import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { DashboardLayout } from './DashboardLayout'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import { defaultUser } from '@/test/handlers'

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('access_token', 'token')
})

describe('DashboardLayout', () => {
  it('renders the navigation and the user email for an authenticated user', async () => {
    renderWithProviders(<DashboardLayout />)

    expect(await screen.findByText(defaultUser.email)).toBeInTheDocument()
    // Nav labels appear in both the sidebar and the mobile bottom nav.
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Subscriptions').length).toBeGreaterThan(0)
  })

  it('hides the admin panel link for non-admin users', async () => {
    server.use(
      http.get('*/auth/me', () =>
        HttpResponse.json({ ...defaultUser, is_admin: false }),
      ),
    )

    renderWithProviders(<DashboardLayout />)

    await screen.findByText(defaultUser.email)
    expect(screen.queryAllByText('Admin Panel')).toHaveLength(0)
  })

  it('shows the admin panel link for admin users', async () => {
    server.use(
      http.get('*/auth/me', () =>
        HttpResponse.json({ ...defaultUser, is_admin: true }),
      ),
    )

    renderWithProviders(<DashboardLayout />)

    await screen.findByText(defaultUser.email)
    expect(screen.getAllByText('Admin Panel').length).toBeGreaterThan(0)
  })
})
