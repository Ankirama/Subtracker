import { describe, it, expect } from 'vitest'
import {
  screen,
  waitForElementToBeRemoved,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import DuplicatesPage from './DuplicatesPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

// The page's DuplicateGroup shape is defined locally in the component; mirror
// the fields the UI reads here.
function buildGroup() {
  return {
    provider: 'Netflix',
    billing_cycle: 'monthly',
    count: 2,
    similar_amounts: true,
    subscriptions: [
      {
        id: 'old',
        provider: 'Netflix',
        amount: 12.99,
        currency: 'EUR',
        billing_cycle: 'monthly',
        custom_label: null,
        created_at: '2026-01-01T00:00:00Z',
        renewal_date: null,
        is_active: true,
        email_count: 5,
      },
      {
        id: 'new',
        provider: 'Netflix',
        amount: 12.99,
        currency: 'EUR',
        billing_cycle: 'monthly',
        custom_label: 'Family',
        created_at: '2026-03-01T00:00:00Z',
        renewal_date: null,
        is_active: false,
        email_count: 2,
      },
    ],
  }
}

function mockDuplicates(groups: unknown[]) {
  server.use(
    http.get('*/subscriptions/duplicates', () => HttpResponse.json(groups)),
  )
}

describe('DuplicatesPage', () => {
  it('shows a loading state while duplicates are fetched', () => {
    server.use(
      http.get('*/subscriptions/duplicates', async () => {
        await delay('infinite')
        return HttpResponse.json([])
      }),
    )

    renderWithProviders(<DuplicatesPage />)

    expect(screen.getByText('Loading duplicates...')).toBeInTheDocument()
  })

  it('shows an error alert when the request fails', async () => {
    server.use(
      http.get('*/subscriptions/duplicates', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<DuplicatesPage />)

    expect(
      await screen.findByText('Error loading duplicates'),
    ).toBeInTheDocument()
  })

  it('shows the empty state when there are no duplicates', async () => {
    mockDuplicates([])

    renderWithProviders(<DuplicatesPage />)

    expect(await screen.findByText('No Duplicates Found')).toBeInTheDocument()
  })

  it('renders a duplicate group with its subscriptions', async () => {
    mockDuplicates([buildGroup()])

    renderWithProviders(<DuplicatesPage />)

    expect(
      await screen.findByRole('heading', { name: 'Netflix' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Similar amounts')).toBeInTheDocument()
    expect(screen.getByText('Family')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Merge Duplicates' }),
    ).toBeInTheDocument()
  })

  it('merges a group: opens the modal, pre-selects target/source, and merges', async () => {
    mockDuplicates([buildGroup()])
    let mergeCall: { sourceId: string; targetId: string } | null = null
    server.use(
      http.post('*/subscriptions/:sourceId/merge/:targetId', ({ params }) => {
        mergeCall = {
          sourceId: params.sourceId as string,
          targetId: params.targetId as string,
        }
        return HttpResponse.json({ success: true, message: 'Merged 2 into 1' })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<DuplicatesPage />)
    await user.click(
      await screen.findByRole('button', { name: 'Merge Duplicates' }),
    )

    // Modal opens with the oldest pre-selected as target, newest as source.
    expect(
      await screen.findByText('Merge Duplicate Subscriptions'),
    ).toBeInTheDocument()
    expect(screen.getByText('Target (Keep)')).toBeInTheDocument()
    expect(screen.getByText('Source (Delete)')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Merge Subscriptions' }))

    expect(await screen.findByText('Merge Successful')).toBeInTheDocument()
    expect(screen.getByText('Merged 2 into 1')).toBeInTheDocument()
    // Newest is the source (deleted), oldest is the target (kept).
    expect(mergeCall).toEqual({ sourceId: 'new', targetId: 'old' })
    await waitForElementToBeRemoved(() =>
      screen.queryByText('Merge Duplicate Subscriptions'),
    )
  })

  it('shows an error toast when the merge fails', async () => {
    mockDuplicates([buildGroup()])
    server.use(
      http.post('*/subscriptions/:sourceId/merge/:targetId', () =>
        HttpResponse.json({ detail: 'nope' }, { status: 500 }),
      ),
    )
    const user = userEvent.setup()

    renderWithProviders(<DuplicatesPage />)
    await user.click(
      await screen.findByRole('button', { name: 'Merge Duplicates' }),
    )
    await screen.findByText('Merge Duplicate Subscriptions')
    await user.click(screen.getByRole('button', { name: 'Merge Subscriptions' }))

    expect(await screen.findByText('Merge Failed')).toBeInTheDocument()
  })
})
