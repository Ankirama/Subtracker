import { describe, it, expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { AdminAnnouncementsPage } from './AdminAnnouncementsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

const TITLE_PLACEHOLDER = 'e.g., Scheduled Maintenance, New Feature Release'
const MESSAGE_PLACEHOLDER = /Enter your announcement message here/

function broadcastResponse(overrides = {}) {
  return {
    success: true,
    announcement_id: 'ann-123',
    notifications_created: 42,
    emails_sent: 40,
    message: 'Broadcast started',
    ...overrides,
  }
}

describe('AdminAnnouncementsPage', () => {
  it('renders the form with the broadcast button disabled', () => {
    renderWithProviders(<AdminAnnouncementsPage />)

    expect(
      screen.getByRole('heading', { name: 'System Announcements' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Broadcast Announcement' }),
    ).toBeDisabled()
  })

  it('keeps the broadcast button disabled when only the title is filled', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminAnnouncementsPage />)

    await user.type(screen.getByPlaceholderText(TITLE_PLACEHOLDER), 'Maintenance')

    expect(
      screen.getByRole('button', { name: 'Broadcast Announcement' }),
    ).toBeDisabled()
  })

  it('broadcasts an announcement and shows the result', async () => {
    let postedBody: unknown = null
    server.use(
      http.post('*/admin/announcements/broadcast', async ({ request }) => {
        postedBody = await request.json()
        return HttpResponse.json(broadcastResponse())
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<AdminAnnouncementsPage />)

    await user.type(screen.getByPlaceholderText(TITLE_PLACEHOLDER), 'Maintenance')
    await user.type(
      screen.getByPlaceholderText(MESSAGE_PLACEHOLDER),
      'Downtime tonight',
    )
    await user.click(
      screen.getByRole('button', { name: 'Broadcast Announcement' }),
    )

    expect(
      await screen.findByText('Announcement Broadcast Started'),
    ).toBeInTheDocument()
    expect(screen.getByText('Last Broadcast Successful')).toBeInTheDocument()
    expect(screen.getByText('Announcement ID: ann-123')).toBeInTheDocument()
    expect(postedBody).toEqual({
      title: 'Maintenance',
      message: 'Downtime tonight',
      priority: 'medium',
      target_all_users: true,
      target_user_ids: [],
    })
    // The form resets after a successful broadcast.
    await waitFor(() =>
      expect(screen.getByPlaceholderText(TITLE_PLACEHOLDER)).toHaveValue(''),
    )
  })

  it('shows an error toast when the broadcast fails', async () => {
    server.use(
      http.post('*/admin/announcements/broadcast', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<AdminAnnouncementsPage />)

    await user.type(screen.getByPlaceholderText(TITLE_PLACEHOLDER), 'Maintenance')
    await user.type(
      screen.getByPlaceholderText(MESSAGE_PLACEHOLDER),
      'Downtime tonight',
    )
    await user.click(
      screen.getByRole('button', { name: 'Broadcast Announcement' }),
    )

    expect(
      await screen.findByText('Error Broadcasting Announcement'),
    ).toBeInTheDocument()
  })

  it('updates the priority badge when the priority changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminAnnouncementsPage />)

    expect(screen.getByText('Medium Priority')).toBeInTheDocument()

    await user.selectOptions(screen.getByRole('combobox'), 'high')

    expect(screen.getByText('High Priority')).toBeInTheDocument()
  })

  it('renders the live markdown preview as the user types', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminAnnouncementsPage />)

    // Preview is hidden until a title is entered.
    expect(
      screen.getByText('Fill in the title and message to see a preview'),
    ).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText(TITLE_PLACEHOLDER), 'Maintenance')
    await user.type(
      screen.getByPlaceholderText(MESSAGE_PLACEHOLDER),
      'Downtime tonight',
    )

    // The MarkdownRenderer paragraph renders the typed message. Scope to the
    // <p> so it doesn't also match the textarea's own value node.
    expect(
      await screen.findByText('Downtime tonight', { selector: 'p' }),
    ).toBeInTheDocument()
  })
})
