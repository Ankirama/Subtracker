import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { Routes, Route } from 'react-router-dom'
import { http, HttpResponse, delay } from 'msw'
import { ProtectedRoute } from './ProtectedRoute'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import { defaultUser } from '@/test/handlers'

function renderGuard() {
  return renderWithProviders(
    <Routes>
      <Route element={<ProtectedRoute />}>
        <Route path="/protected" element={<div>Protected content</div>} />
      </Route>
      <Route path="/login" element={<div>Login page</div>} />
    </Routes>,
    { route: '/protected' },
  )
}

beforeEach(() => localStorage.clear())

describe('ProtectedRoute', () => {
  it('shows a spinner while authentication is loading', () => {
    localStorage.setItem('access_token', 'token')
    server.use(
      http.get('*/auth/me', async () => {
        await delay('infinite')
        return HttpResponse.json(defaultUser)
      }),
    )

    renderGuard()

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the outlet when authenticated', async () => {
    localStorage.setItem('access_token', 'token')

    renderGuard()

    expect(await screen.findByText('Protected content')).toBeInTheDocument()
  })

  it('redirects to login when not authenticated', async () => {
    renderGuard()

    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })
})
