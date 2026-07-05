import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { SubscriptionFeedbackModal } from './SubscriptionFeedbackModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Subscription } from '@/types'

function buildSubscription(overrides: Partial<Subscription> = {}): Subscription {
  return {
    id: 'sub-1',
    user_id: 'user-1',
    mailbox_id: null,
    provider: 'Netflix',
    email_sender: null,
    amount: 12.99,
    currency: 'EUR',
    billing_cycle: 'monthly',
    renewal_date: null,
    next_renewal_date: null,
    next_billing_date: null,
    is_active: true,
    category: 'streaming',
    tags: null,
    custom_label: null,
    notes: null,
    confidence_score: 0.9,
    extraction_method: 'ai',
    payment_processor: null,
    first_detected_at: '2026-01-01T00:00:00Z',
    last_confirmed_at: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    suggested_cancellation_status: null,
    cancellation_suggestion_reason: null,
    cancellation_suggestion_created_at: null,
    ...overrides,
  }
}

function renderModal(
  props: Partial<Parameters<typeof SubscriptionFeedbackModal>[0]> = {},
) {
  const onClose = vi.fn()
  const onFeedbackSubmitted = vi.fn()
  renderWithProviders(
    <SubscriptionFeedbackModal
      isOpen
      onClose={onClose}
      subscription={buildSubscription()}
      onFeedbackSubmitted={onFeedbackSubmitted}
      {...props}
    />,
  )
  return { onClose, onFeedbackSubmitted }
}

describe('SubscriptionFeedbackModal', () => {
  it('renders the feedback options for the subscription', async () => {
    renderModal()

    expect(
      await screen.findByText('Why are you removing this subscription?'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Subscription:/)).toHaveTextContent('Netflix')
    expect(screen.getByRole('radio', { name: /Duplicate/ })).toBeInTheDocument()
  })

  it('disables the submit button until a reason is selected', async () => {
    const user = userEvent.setup()
    renderModal()
    await screen.findByText('Why are you removing this subscription?')

    const submit = screen.getByRole('button', { name: 'Submit & Delete' })
    expect(submit).toBeDisabled()

    await user.click(screen.getByRole('radio', { name: /Duplicate/ }))

    expect(submit).toBeEnabled()
  })

  it('submits the selected feedback and closes on success', async () => {
    let body: Record<string, unknown> | null = null
    server.use(
      http.post('*/subscriptions/feedback', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({})
      }),
    )
    const user = userEvent.setup()
    const { onClose, onFeedbackSubmitted } = renderModal()
    await screen.findByText('Why are you removing this subscription?')

    await user.click(screen.getByRole('radio', { name: /Duplicate/ }))
    await user.click(screen.getByRole('button', { name: 'Submit & Delete' }))

    expect(
      await screen.findByText('Thank you for your feedback!'),
    ).toBeInTheDocument()
    expect(body).toMatchObject({
      subscription_id: 'sub-1',
      feedback_type: 'duplicate',
    })
    expect(onFeedbackSubmitted).toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })

  it('includes the additional details text in the submission', async () => {
    let body: Record<string, unknown> | null = null
    server.use(
      http.post('*/subscriptions/feedback', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({})
      }),
    )
    const user = userEvent.setup()
    renderModal()
    await screen.findByText('Why are you removing this subscription?')

    await user.click(screen.getByRole('radio', { name: /Other/ }))
    await user.type(
      screen.getByPlaceholderText(/Any additional information/),
      'It is a one-off payment',
    )
    await user.click(screen.getByRole('button', { name: 'Submit & Delete' }))

    await screen.findByText('Thank you for your feedback!')
    expect(body).toMatchObject({
      feedback_type: 'other',
      feedback_text: 'It is a one-off payment',
    })
  })

  it('shows an error toast and stays open when submission fails', async () => {
    server.use(
      http.post('*/subscriptions/feedback', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    const user = userEvent.setup()
    const { onClose, onFeedbackSubmitted } = renderModal()
    await screen.findByText('Why are you removing this subscription?')

    await user.click(screen.getByRole('radio', { name: /Duplicate/ }))
    await user.click(screen.getByRole('button', { name: 'Submit & Delete' }))

    expect(
      await screen.findByText('Failed to submit feedback'),
    ).toBeInTheDocument()
    expect(onFeedbackSubmitted).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup()
    const { onClose } = renderModal()
    await screen.findByText('Why are you removing this subscription?')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
  })
})
