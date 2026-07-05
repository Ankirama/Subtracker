import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { SecuritySettingsTab } from './SecuritySettingsTab'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

// The embedded TwoFactorSettingsPage renders Chakra Radio / autoFocus-modal
// inputs that trip the Chakra/jsdom focus-trap commit error (same limitation as
// the Switch-in-modal admin pages). Stub it so this tab's own password-change
// logic is testable in isolation.
vi.mock('./TwoFactorSettingsPage', () => ({
  TwoFactorSettingsPage: () => null,
}))

async function fillPasswords(
  user: ReturnType<typeof userEvent.setup>,
  { current, next, confirm }: { current: string; next: string; confirm: string },
) {
  await user.type(screen.getByPlaceholderText('Enter current password'), current)
  await user.type(
    screen.getByPlaceholderText('Enter new password (min 8 characters)'),
    next,
  )
  await user.type(screen.getByPlaceholderText('Confirm new password'), confirm)
}

describe('SecuritySettingsTab', () => {
  it('renders the change password form', () => {
    renderWithProviders(<SecuritySettingsTab />, { withAuth: false })

    expect(
      screen.getByRole('heading', { name: 'Change Password' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Change Password' }),
    ).toBeInTheDocument()
  })

  it('warns when fields are missing', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SecuritySettingsTab />, { withAuth: false })

    await user.click(screen.getByRole('button', { name: 'Change Password' }))

    expect(await screen.findByText('Missing fields')).toBeInTheDocument()
  })

  it('warns when the new passwords do not match', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SecuritySettingsTab />, { withAuth: false })

    await fillPasswords(user, {
      current: 'oldpass12',
      next: 'newpass12',
      confirm: 'different12',
    })
    await user.click(screen.getByRole('button', { name: 'Change Password' }))

    expect(
      await screen.findByText('Passwords do not match'),
    ).toBeInTheDocument()
  })

  it('warns when the new password is too short', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SecuritySettingsTab />, { withAuth: false })

    await fillPasswords(user, { current: 'oldpass12', next: 'short', confirm: 'short' })
    await user.click(screen.getByRole('button', { name: 'Change Password' }))

    expect(await screen.findByText('Password too short')).toBeInTheDocument()
  })

  it('changes the password with valid input', async () => {
    let putBody: unknown = null
    server.use(
      http.put('*/auth/me/password', async ({ request }) => {
        putBody = await request.json()
        return HttpResponse.json({ message: 'ok' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SecuritySettingsTab />, { withAuth: false })

    await fillPasswords(user, {
      current: 'oldpass12',
      next: 'newpass12',
      confirm: 'newpass12',
    })
    await user.click(screen.getByRole('button', { name: 'Change Password' }))

    expect(await screen.findByText('Password changed')).toBeInTheDocument()
    expect(putBody).toEqual({
      current_password: 'oldpass12',
      new_password: 'newpass12',
    })
  })
})
