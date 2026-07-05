import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { Routes, Route } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { VerifyEmailPage } from './VerifyEmailPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

// The success path schedules a delayed navigate('/dashboard'); spy on it so the
// timer fires harmlessly instead of navigating a real (unmounted) router tree.
const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }))
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateMock }
})

function renderAtToken(token: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/verify-email/:token" element={<VerifyEmailPage />} />
    </Routes>,
    { route: `/verify-email/${token}`, withAuth: false },
  )
}

beforeEach(() => {
  localStorage.clear()
  navigateMock.mockReset()
})

describe('VerifyEmailPage', () => {
  it('verifies the email and stores the tokens', async () => {
    server.use(
      http.post('*/auth/verify-email', () =>
        HttpResponse.json({
          access_token: 'tok-access',
          refresh_token: 'tok-refresh',
          token_type: 'bearer',
        }),
      ),
    )

    renderAtToken('good-token')

    expect(
      await screen.findByText('Email Verified Successfully!'),
    ).toBeInTheDocument()
    expect(localStorage.getItem('access_token')).toBe('tok-access')
    expect(localStorage.getItem('refresh_token')).toBe('tok-refresh')
  })

  it('shows the failure state when verification fails', async () => {
    server.use(
      http.post('*/auth/verify-email', () =>
        HttpResponse.json({ detail: 'Token expired' }, { status: 400 }),
      ),
    )

    renderAtToken('bad-token')

    expect(await screen.findByText('Verification Failed')).toBeInTheDocument()
    expect(screen.getByText('Token expired')).toBeInTheDocument()
  })

  it('shows an error when there is no token in the URL', async () => {
    // Rendered outside a matching Route, so useParams yields no token.
    renderWithProviders(<VerifyEmailPage />, { withAuth: false })

    expect(
      await screen.findByText('Invalid verification link - no token provided'),
    ).toBeInTheDocument()
  })
})
