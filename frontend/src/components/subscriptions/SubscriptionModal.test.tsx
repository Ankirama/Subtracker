import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { SubscriptionModal } from './SubscriptionModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Subscription } from '@/types'
import type { CategoriesListResponse } from '@/api/categories'

const categories: CategoriesListResponse = {
  categories: [
    {
      id: null,
      name: 'other',
      display_name: 'Other',
      color: 'gray',
      is_default: true,
      user_id: null,
      created_at: null,
      updated_at: null,
    },
    {
      id: null,
      name: 'streaming',
      display_name: 'Streaming',
      color: 'purple',
      is_default: true,
      user_id: null,
      created_at: null,
      updated_at: null,
    },
  ],
  total: 2,
}

function mockCategories() {
  server.use(http.get('*/categories', () => HttpResponse.json(categories)))
}

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
    renewal_date: '2026-08-01T00:00:00Z',
    next_renewal_date: null,
    next_billing_date: null,
    is_active: true,
    category: 'streaming',
    tags: null,
    custom_label: 'Family plan',
    notes: null,
    confidence_score: 0.9,
    extraction_method: 'manual',
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

const PROVIDER_PLACEHOLDER = 'e.g., Netflix, Spotify'

describe('SubscriptionModal', () => {
  it('shows the create title, button, and no active switch for a new subscription', async () => {
    mockCategories()

    renderWithProviders(
      <SubscriptionModal isOpen onClose={vi.fn()} subscription={null} />,
    )

    expect(await screen.findByText('Add Subscription')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Create Subscription' }),
    ).toBeInTheDocument()
    // The active-status Switch (a checkbox) is edit-only.
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('prefills the form and shows the edit affordances when editing', async () => {
    mockCategories()

    renderWithProviders(
      <SubscriptionModal
        isOpen
        onClose={vi.fn()}
        subscription={buildSubscription()}
      />,
    )

    expect(await screen.findByText('Edit Subscription')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(PROVIDER_PLACEHOLDER)).toHaveValue(
      'Netflix',
    )
    expect(screen.getByDisplayValue('Family plan')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Save Changes' }),
    ).toBeInTheDocument()
    // Chakra's Switch renders as an <input type="checkbox">.
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })

  it('creates a subscription and closes the modal on success', async () => {
    mockCategories()
    const onClose = vi.fn()
    let createdBody: Record<string, unknown> | null = null
    server.use(
      http.post('*/subscriptions', async ({ request }) => {
        createdBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(buildSubscription({ id: 'new' }))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(
      <SubscriptionModal isOpen onClose={onClose} subscription={null} />,
    )
    await screen.findByText('Add Subscription')

    await user.type(
      screen.getByPlaceholderText(PROVIDER_PLACEHOLDER),
      'Disney+',
    )
    await user.type(screen.getByPlaceholderText('0.00'), '9.99')
    await user.click(screen.getByRole('button', { name: 'Create Subscription' }))

    expect(await screen.findByText('Subscription created')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalled()
    expect(createdBody).toMatchObject({ provider: 'Disney+', amount: 9.99 })
  })

  it('shows an error toast and keeps the modal open when creation fails', async () => {
    mockCategories()
    const onClose = vi.fn()
    server.use(
      http.post('*/subscriptions', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(
      <SubscriptionModal isOpen onClose={onClose} subscription={null} />,
    )
    await screen.findByText('Add Subscription')

    await user.type(screen.getByPlaceholderText(PROVIDER_PLACEHOLDER), 'Hulu')
    await user.click(screen.getByRole('button', { name: 'Create Subscription' }))

    expect(
      await screen.findByText('Failed to create subscription'),
    ).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('updates an existing subscription on save', async () => {
    mockCategories()
    const onClose = vi.fn()
    let updatedId: string | null = null
    let updatedBody: Record<string, unknown> | null = null
    server.use(
      http.put('*/subscriptions/sub-1', async ({ request }) => {
        updatedId = 'sub-1'
        updatedBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(buildSubscription())
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(
      <SubscriptionModal
        isOpen
        onClose={onClose}
        subscription={buildSubscription()}
      />,
    )
    await screen.findByText('Edit Subscription')

    const providerInput = screen.getByPlaceholderText(PROVIDER_PLACEHOLDER)
    await user.clear(providerInput)
    await user.type(providerInput, 'Netflix Premium')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText('Subscription updated')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalled()
    expect(updatedId).toBe('sub-1')
    expect(updatedBody).toMatchObject({ provider: 'Netflix Premium' })
  })

  it('calls onClose when Cancel is clicked', async () => {
    mockCategories()
    const onClose = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(
      <SubscriptionModal isOpen onClose={onClose} subscription={null} />,
    )
    await screen.findByText('Add Subscription')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
  })
})
