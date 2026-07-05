import { describe, it, expect } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { ReviewEmailsTab } from './ReviewEmailsTab'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { EmailDetailResponse, UncertainEmail } from '@/types'

function buildEmail(overrides: Partial<UncertainEmail> = {}): UncertainEmail {
  return {
    id: 'e1',
    subject: 'Maybe a Netflix charge',
    sender: 'billing@netflix.com',
    sender_name: 'Netflix',
    date: '2026-05-01T10:00:00Z',
    classification_confidence: 0.6,
    is_subscription: true,
    has_linked_subscription: false,
    preview: 'Your receipt',
    ...overrides,
  }
}

function uncertainResponse(emails: UncertainEmail[]) {
  return {
    emails,
    total: emails.length,
    uncertain_classified: emails.length,
    extraction_failed: 0,
  }
}

function mockUncertain(emails: UncertainEmail[]) {
  server.use(
    http.get('*/ai-sandbox/uncertain-emails', () =>
      HttpResponse.json(uncertainResponse(emails)),
    ),
  )
}

const emailDetail: EmailDetailResponse = {
  id: 'e1',
  subject: 'Maybe a Netflix charge',
  sender: 'billing@netflix.com',
  sender_name: 'Netflix',
  recipient: 'me@acme.com',
  date: '2026-05-01T10:00:00Z',
  body_text: 'Thanks',
  body_html: null,
  is_subscription: true,
  classification_confidence: 0.6,
  classification_reasoning: null,
  has_linked_subscription: false,
  linked_subscription_id: null,
}

describe('ReviewEmailsTab', () => {
  it('shows a loading spinner while uncertain emails load', () => {
    server.use(
      http.get('*/ai-sandbox/uncertain-emails', async () => {
        await delay('infinite')
        return HttpResponse.json(uncertainResponse([]))
      }),
    )

    renderWithProviders(<ReviewEmailsTab />, { withAuth: false })

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the uncertain emails table', async () => {
    mockUncertain([buildEmail()])

    renderWithProviders(<ReviewEmailsTab />, { withAuth: false })

    expect(
      await screen.findByText('Maybe a Netflix charge'),
    ).toBeInTheDocument()
    expect(screen.getByText('billing@netflix.com')).toBeInTheDocument()
  })

  it('shows the empty state when there are no uncertain emails', async () => {
    mockUncertain([])

    renderWithProviders(<ReviewEmailsTab />, { withAuth: false })

    expect(
      await screen.findByText(/No uncertain emails found/),
    ).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    server.use(
      http.get('*/ai-sandbox/uncertain-emails', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<ReviewEmailsTab />, { withAuth: false })

    expect(
      await screen.findByText('Failed to load uncertain emails'),
    ).toBeInTheDocument()
  })

  it('opens the detail modal when an email is reviewed', async () => {
    mockUncertain([buildEmail()])
    server.use(
      http.get('*/ai-sandbox/email/e1', () => HttpResponse.json(emailDetail)),
    )
    const user = userEvent.setup()

    renderWithProviders(<ReviewEmailsTab />, { withAuth: false })
    await screen.findByText('Maybe a Netflix charge')

    await user.click(screen.getByRole('button', { name: 'Review' }))

    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByText('Email Details')).toBeInTheDocument()
  })

  it('bulk-marks selected emails as not subscriptions', async () => {
    let bulkBody: unknown = null
    mockUncertain([buildEmail()])
    server.use(
      http.post('*/ai-sandbox/bulk-mark-not-subscription', async ({ request }) => {
        bulkBody = await request.json()
        return HttpResponse.json({
          success: true,
          processed: 1,
          failed: 0,
          errors: [],
        })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<ReviewEmailsTab />, { withAuth: false })
    await screen.findByText('Maybe a Netflix charge')

    // First checkbox is the header select-all; the second is the row.
    await user.click(screen.getAllByRole('checkbox')[1])
    await user.click(
      await screen.findByRole('button', { name: 'Mark as Not Subscription' }),
    )

    expect(
      await screen.findByText('Bulk operation completed'),
    ).toBeInTheDocument()
    expect(bulkBody).toEqual({ email_ids: ['e1'] })
  })
})
