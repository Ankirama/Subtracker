import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { Routes, Route } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { AdminRoute } from './AdminRoute'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import { defaultUser } from '@/test/handlers'

function renderGuard() {
  return renderWithProviders(
    <Routes>
      <Route
        path="/admin"
        element={
          <AdminRoute>
            <div>Admin content</div>
          </AdminRoute>
        }
      />
      <Route path="/login" element={<div>Login page</div>} />
    </Routes>,
    { route: '/admin' },
  )
}

beforeEach(() => localStorage.clear())

describe('AdminRoute', () => {
  it('renders the children for an admin user', async () => {
    localStorage.setItem('access_token', 'token')
    server.use(
      http.get('*/auth/me', () =>
        HttpResponse.json({ ...defaultUser, is_admin: true }),
      ),
    )

    renderGuard()

    expect(await screen.findByText('Admin content')).toBeInTheDocument()
  })

  it('shows access denied for a non-admin user', async () => {
    localStorage.setItem('access_token', 'token')
    server.use(
      http.get('*/auth/me', () =>
        HttpResponse.json({ ...defaultUser, is_admin: false }),
      ),
    )

    renderGuard()

    expect(await screen.findByText('Access Denied')).toBeInTheDocument()
    expect(screen.queryByText('Admin content')).not.toBeInTheDocument()
  })

  it('redirects to login when not authenticated', async () => {
    renderGuard()

    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })
})
