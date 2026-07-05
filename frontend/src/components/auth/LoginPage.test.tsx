import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { LoginPage } from './LoginPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

beforeEach(() => localStorage.clear())

// NOTE: the 2FA verification sub-form is intentionally not covered. Its code
// input uses autoFocus; when Chakra's focus-visible tracking reassigns the
// focused element's `focus`, jsdom (which marks it getter-only) throws in
// React's commit phase — the same environment limitation seen with Switch-in-
// modal admin pages. The primary login path (success + error) is covered below.

async function fillCredentials(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText('your@email.com'), 'user@example.com')
  await user.type(screen.getAllByPlaceholderText('Password')[0], 'secret123')
}

describe('LoginPage', () => {
  it('renders the login form', () => {
    renderWithProviders(<LoginPage />)

    expect(
      screen.getByRole('heading', { name: 'Welcome Back' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument()
  })

  it('logs in and stores the tokens', async () => {
    let postedBody: unknown = null
    server.use(
      http.post('*/auth/login', async ({ request }) => {
        postedBody = await request.json()
        return HttpResponse.json({
          access_token: 'tok-access',
          refresh_token: 'tok-refresh',
          token_type: 'bearer',
        })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />)

    await fillCredentials(user)
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    expect(await screen.findByText('Login successful')).toBeInTheDocument()
    expect(localStorage.getItem('access_token')).toBe('tok-access')
    expect(localStorage.getItem('refresh_token')).toBe('tok-refresh')
    expect(postedBody).toEqual({
      email: 'user@example.com',
      password: 'secret123',
    })
  })

  it('shows an error on invalid credentials', async () => {
    // Use 400 (not 401) so the response reaches the component instead of the
    // API client's 401 refresh/redirect interceptor.
    server.use(
      http.post('*/auth/login', () =>
        HttpResponse.json({ detail: 'Incorrect email or password' }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />)

    await fillCredentials(user)
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    // The detail message appears in both the error Alert and the toast.
    const matches = await screen.findAllByText('Incorrect email or password')
    expect(matches.length).toBeGreaterThan(0)
    expect(localStorage.getItem('access_token')).toBeNull()
  })
})
