import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { ResendVerificationPage } from './ResendVerificationPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

describe('ResendVerificationPage', () => {
  it('renders the resend form', () => {
    renderWithProviders(<ResendVerificationPage />, { withAuth: false })

    expect(
      screen.getByRole('heading', { name: 'Resend Verification' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Send Verification Email' }),
    ).toBeInTheDocument()
  })

  it('sends a verification email and shows the success view', async () => {
    let postedBody: unknown = null
    server.use(
      http.post('*/auth/resend-verification', async ({ request }) => {
        postedBody = await request.json()
        return HttpResponse.json({ message: 'Verification email sent' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<ResendVerificationPage />, { withAuth: false })

    await user.type(
      screen.getByPlaceholderText('your@email.com'),
      'user@example.com',
    )
    await user.click(
      screen.getByRole('button', { name: 'Send Verification Email' }),
    )

    // The heading is prefixed with an emoji (📬), so match by substring.
    expect(
      await screen.findByRole('heading', { name: /Check Your Email/ }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Verification email sent successfully!'),
    ).toBeInTheDocument()
    expect(postedBody).toEqual({ email: 'user@example.com' })
  })

  it('shows an error when the request fails', async () => {
    server.use(
      http.post('*/auth/resend-verification', () =>
        HttpResponse.json({ detail: 'Email not found' }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<ResendVerificationPage />, { withAuth: false })

    await user.type(
      screen.getByPlaceholderText('your@email.com'),
      'user@example.com',
    )
    await user.click(
      screen.getByRole('button', { name: 'Send Verification Email' }),
    )

    // The detail message appears in both the error Alert and the toast.
    const matches = await screen.findAllByText('Email not found')
    expect(matches.length).toBeGreaterThan(0)
  })
})
