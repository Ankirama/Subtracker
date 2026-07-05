import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { BudgetModal } from './BudgetModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { Budget } from '@/api/budgets'

function buildBudget(overrides: Partial<Budget> = {}): Budget {
  return {
    id: 'budget-1',
    user_id: 'user-1',
    name: 'Streaming',
    category: 'streaming',
    period: 'monthly',
    limit_amount: 30,
    currency: 'EUR',
    alert_threshold: 75,
    alert_enabled: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const NAME_PLACEHOLDER = 'e.g., Entertainment Budget'

describe('BudgetModal', () => {
  it('shows the create title and button for a new budget', async () => {
    renderWithProviders(<BudgetModal isOpen onClose={vi.fn()} budget={null} />)

    expect(await screen.findByText('Create Budget')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()
  })

  it('prefills the form and shows the edit affordances when editing', async () => {
    renderWithProviders(
      <BudgetModal isOpen onClose={vi.fn()} budget={buildBudget()} />,
    )

    expect(await screen.findByText('Edit Budget')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(NAME_PLACEHOLDER)).toHaveValue('Streaming')
    expect(screen.getByRole('button', { name: 'Update' })).toBeInTheDocument()
  })

  it('blocks submission with a validation toast when the name is empty', async () => {
    let created = false
    server.use(
      http.post('*/budgets', () => {
        created = true
        return HttpResponse.json(buildBudget())
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<BudgetModal isOpen onClose={vi.fn()} budget={null} />)
    await screen.findByText('Create Budget')

    await user.click(screen.getByRole('button', { name: 'Create' }))

    expect(await screen.findByText('Validation error')).toBeInTheDocument()
    expect(created).toBe(false)
  })

  it('creates a budget and closes the modal on success', async () => {
    const onClose = vi.fn()
    let createdBody: Record<string, unknown> | null = null
    server.use(
      http.post('*/budgets', async ({ request }) => {
        createdBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(buildBudget({ id: 'new' }))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<BudgetModal isOpen onClose={onClose} budget={null} />)
    await screen.findByText('Create Budget')

    await user.type(
      screen.getByPlaceholderText(NAME_PLACEHOLDER),
      'Music Budget',
    )
    await user.click(screen.getByRole('button', { name: 'Create' }))

    expect(await screen.findByText('Budget created')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalled()
    expect(createdBody).toMatchObject({ name: 'Music Budget', limit_amount: 50 })
  })

  it('shows an error toast and keeps the modal open when creation fails', async () => {
    const onClose = vi.fn()
    server.use(
      http.post('*/budgets', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<BudgetModal isOpen onClose={onClose} budget={null} />)
    await screen.findByText('Create Budget')

    await user.type(screen.getByPlaceholderText(NAME_PLACEHOLDER), 'Gaming')
    await user.click(screen.getByRole('button', { name: 'Create' }))

    expect(
      await screen.findByText('Failed to create budget'),
    ).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('updates an existing budget on save', async () => {
    const onClose = vi.fn()
    let updatedId: string | null = null
    let updatedBody: Record<string, unknown> | null = null
    server.use(
      http.put('*/budgets/budget-1', async ({ request }) => {
        updatedId = 'budget-1'
        updatedBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(buildBudget())
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(
      <BudgetModal isOpen onClose={onClose} budget={buildBudget()} />,
    )
    await screen.findByText('Edit Budget')

    const nameInput = screen.getByPlaceholderText(NAME_PLACEHOLDER)
    await user.clear(nameInput)
    await user.type(nameInput, 'Streaming Plus')
    await user.click(screen.getByRole('button', { name: 'Update' }))

    expect(await screen.findByText('Budget updated')).toBeInTheDocument()
    expect(onClose).toHaveBeenCalled()
    expect(updatedId).toBe('budget-1')
    expect(updatedBody).toMatchObject({ name: 'Streaming Plus' })
  })

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(<BudgetModal isOpen onClose={onClose} budget={null} />)
    await screen.findByText('Create Budget')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
  })
})
