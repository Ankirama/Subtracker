import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { RegisterPage } from './RegisterPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

async function fillForm(
  user: ReturnType<typeof userEvent.setup>,
  { password, confirm }: { password: string; confirm: string },
) {
  await user.type(screen.getByPlaceholderText('Enter your invite token'), 'INV-1')
  await user.type(screen.getByPlaceholderText('your@email.com'), 'new@example.com')
  await user.type(screen.getByPlaceholderText('Password'), password)
  await user.type(screen.getByPlaceholderText('Confirm password'), confirm)
}

describe('RegisterPage', () => {
  it('renders the registration form', () => {
    renderWithProviders(<RegisterPage />, { withAuth: false })

    expect(
      screen.getByRole('heading', { name: 'Create Account' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Create Account' }),
    ).toBeInTheDocument()
  })

  it('rejects mismatched passwords', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RegisterPage />, { withAuth: false })

    await fillForm(user, { password: 'password123', confirm: 'different123' })
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    expect(
      await screen.findByText('Passwords do not match'),
    ).toBeInTheDocument()
  })

  it('rejects passwords that are too short', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RegisterPage />, { withAuth: false })

    await fillForm(user, { password: 'short', confirm: 'short' })
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    expect(
      await screen.findByText('Password must be at least 8 characters'),
    ).toBeInTheDocument()
  })

  it('registers successfully and shows the verify-email view', async () => {
    let postedBody: Record<string, unknown> | null = null
    server.use(
      http.post('*/auth/register', async ({ request }) => {
        postedBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({
          email: 'new@example.com',
          message: 'Registration successful',
        })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<RegisterPage />, { withAuth: false })

    await fillForm(user, { password: 'password123', confirm: 'password123' })
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    // The heading is prefixed with an emoji (📬), so match by substring.
    expect(
      await screen.findByRole('heading', { name: /Verify Your Email/ }),
    ).toBeInTheDocument()
    // The success string appears in both the Alert and the toast.
    expect(
      screen.getAllByText('Registration successful! Please check your email.')
        .length,
    ).toBeGreaterThan(0)
    expect(postedBody).toMatchObject({
      email: 'new@example.com',
      invite_token: 'INV-1',
    })
  })

  it('pre-fills the invite token from the URL', () => {
    renderWithProviders(<RegisterPage />, {
      route: '/register?token=INV-FROM-URL',
      withAuth: false,
    })

    const inviteInput = screen.getByPlaceholderText('Enter your invite token')
    expect(inviteInput).toHaveValue('INV-FROM-URL')
    expect(inviteInput).toHaveAttribute('readonly')
  })
})
