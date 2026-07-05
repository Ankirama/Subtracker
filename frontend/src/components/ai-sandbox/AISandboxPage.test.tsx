import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { AISandboxPage } from './AISandboxPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

function mockUncertainEmpty() {
  // The Review tab panel mounts alongside the Manual tab, so its query fires.
  server.use(
    http.get('*/ai-sandbox/uncertain-emails', () =>
      HttpResponse.json({
        emails: [],
        total: 0,
        uncertain_classified: 0,
        extraction_failed: 0,
      }),
    ),
  )
}

describe('AISandboxPage', () => {
  it('renders the sandbox with both tabs', () => {
    mockUncertainEmpty()

    renderWithProviders(<AISandboxPage />, { withAuth: false })

    expect(screen.getByRole('heading', { name: 'AI Sandbox' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Manual Test' })).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: 'Review Uncertain Emails' }),
    ).toBeInTheDocument()
  })

  it('switches to the review tab', async () => {
    mockUncertainEmpty()
    const user = userEvent.setup()

    renderWithProviders(<AISandboxPage />, { withAuth: false })

    await user.click(screen.getByRole('tab', { name: 'Review Uncertain Emails' }))

    expect(
      await screen.findByText(/No uncertain emails found/),
    ).toBeInTheDocument()
  })
})
