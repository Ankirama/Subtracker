import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { ManualTestTab } from './ManualTestTab'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

async function fillEmail(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText('Email subject line'), 'Your receipt')
  await user.type(
    screen.getByPlaceholderText('sender@example.com'),
    'billing@netflix.com',
  )
}

describe('ManualTestTab', () => {
  it('renders the email content form', () => {
    renderWithProviders(<ManualTestTab />, { withAuth: false })

    expect(screen.getByText('Email Content')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Test Classification' }),
    ).toBeInTheDocument()
  })

  it('warns when the subject or sender is missing', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ManualTestTab />, { withAuth: false })

    await user.click(screen.getByRole('button', { name: 'Test Classification' }))

    expect(
      await screen.findByText('Subject and sender are required'),
    ).toBeInTheDocument()
  })

  it('runs a classification test and shows the result', async () => {
    server.use(
      http.post('*/ai-sandbox/test-classification', () =>
        HttpResponse.json({
          is_subscription: true,
          confidence: 0.92,
          reasoning: 'Looks like a receipt',
          category: 'streaming',
        }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<ManualTestTab />, { withAuth: false })

    await fillEmail(user)
    await user.click(screen.getByRole('button', { name: 'Test Classification' }))

    expect(
      await screen.findByText('Classification Results'),
    ).toBeInTheDocument()
    expect(screen.getByText('YES')).toBeInTheDocument()
  })

  it('runs an extraction test and shows the result', async () => {
    server.use(
      http.post('*/ai-sandbox/test-extraction', () =>
        HttpResponse.json({
          provider: 'Netflix',
          amount: 9.99,
          currency: 'EUR',
          billing_cycle: 'monthly',
          renewal_date: null,
          custom_label: null,
          category: 'streaming',
          confidence_score: 0.88,
          extraction_method: 'ai',
          raw_response: null,
        }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<ManualTestTab />, { withAuth: false })

    await fillEmail(user)
    await user.click(screen.getByRole('button', { name: 'Test Extraction' }))

    expect(await screen.findByText('Extraction Results')).toBeInTheDocument()
    expect(screen.getByText('Netflix')).toBeInTheDocument()
  })
})
