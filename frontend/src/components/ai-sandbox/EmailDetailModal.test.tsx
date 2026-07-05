import { describe, it, expect, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EmailDetailModal } from './EmailDetailModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import type { EmailDetailResponse } from '@/types'

function buildEmail(overrides: Partial<EmailDetailResponse> = {}): EmailDetailResponse {
  return {
    id: 'e1',
    subject: 'Netflix receipt',
    sender: 'billing@netflix.com',
    sender_name: 'Netflix',
    recipient: 'me@acme.com',
    date: '2026-05-01T10:00:00Z',
    body_text: 'Thanks for your payment',
    body_html: null,
    is_subscription: true,
    classification_confidence: 0.9,
    classification_reasoning: null,
    has_linked_subscription: false,
    linked_subscription_id: null,
    ...overrides,
  }
}

function renderModal(props: Partial<React.ComponentProps<typeof EmailDetailModal>> = {}) {
  return renderWithProviders(
    <EmailDetailModal
      email={buildEmail()}
      isOpen
      onClose={vi.fn()}
      onMarkNotSubscription={vi.fn()}
      onCreateSubscription={vi.fn()}
      isMarkPending={false}
      {...props}
    />,
    { withAuth: false },
  )
}

describe('EmailDetailModal', () => {
  it('renders the email details', async () => {
    renderModal()

    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText('Email Details')).toBeInTheDocument()
    expect(dialog.getByText('Netflix receipt')).toBeInTheDocument()
    expect(dialog.getByText('billing@netflix.com')).toBeInTheDocument()
  })

  it('calls onCreateSubscription when the create button is clicked', async () => {
    const onCreateSubscription = vi.fn()
    renderModal({ onCreateSubscription })
    const user = userEvent.setup()

    await user.click(
      await screen.findByRole('button', { name: 'Create Subscription' }),
    )

    expect(onCreateSubscription).toHaveBeenCalledTimes(1)
  })

  it('calls onMarkNotSubscription when the not-a-subscription button is clicked', async () => {
    const onMarkNotSubscription = vi.fn()
    renderModal({ onMarkNotSubscription })
    const user = userEvent.setup()

    await user.click(
      await screen.findByRole('button', { name: 'Not a Subscription' }),
    )

    expect(onMarkNotSubscription).toHaveBeenCalledTimes(1)
  })

  it('hides the create button when the email already has a linked subscription', async () => {
    renderModal({ email: buildEmail({ has_linked_subscription: true }) })

    await screen.findByRole('dialog')
    expect(
      screen.queryByRole('button', { name: 'Create Subscription' }),
    ).not.toBeInTheDocument()
  })
})
