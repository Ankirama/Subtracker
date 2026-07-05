import { describe, it, expect, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CreateSubscriptionModal } from './CreateSubscriptionModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import type { EmailDetailResponse } from '@/types'

const email = { id: 'e1' } as EmailDetailResponse

function renderModal(props: Partial<React.ComponentProps<typeof CreateSubscriptionModal>> = {}) {
  return renderWithProviders(
    <CreateSubscriptionModal
      email={email}
      isOpen
      onClose={vi.fn()}
      onSubmit={vi.fn()}
      isSubmitting={false}
      {...props}
    />,
    { withAuth: false },
  )
}

describe('CreateSubscriptionModal', () => {
  it('renders the form', async () => {
    renderModal()

    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText('Create Subscription Manually')).toBeInTheDocument()
    expect(
      dialog.getByRole('button', { name: 'Create Subscription' }),
    ).toBeInTheDocument()
  })

  it('warns and does not submit when the provider is empty', async () => {
    const onSubmit = vi.fn()
    renderModal({ onSubmit })
    const user = userEvent.setup()

    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Create Subscription' }))

    expect(await screen.findByText('Provider is required')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits the subscription with the entered data', async () => {
    const onSubmit = vi.fn()
    renderModal({ onSubmit })
    const user = userEvent.setup()

    const dialog = within(await screen.findByRole('dialog'))
    await user.type(
      dialog.getByPlaceholderText('Service name (e.g., Netflix, Spotify)'),
      'Netflix',
    )
    await user.type(dialog.getByPlaceholderText('9.99'), '9.99')
    await user.click(dialog.getByRole('button', { name: 'Create Subscription' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        email_id: 'e1',
        provider: 'Netflix',
        amount: 9.99,
        currency: 'EUR',
        billing_cycle: 'monthly',
        category: 'other',
      }),
    )
  })
})
