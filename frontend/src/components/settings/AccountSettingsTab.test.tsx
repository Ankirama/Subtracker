import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { AccountSettingsTab } from './AccountSettingsTab'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

vi.mock('../../contexts/AuthContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../contexts/AuthContext')>()
  return {
    ...actual,
    useAuth: () => ({
      user: {
        id: 'u1',
        email: 'alice@example.com',
        display_name: 'Alice',
        is_admin: false,
      },
    }),
  }
})

beforeEach(() => localStorage.clear())

describe('AccountSettingsTab', () => {
  it('renders the profile form prefilled with the user data', () => {
    renderWithProviders(<AccountSettingsTab />, { withAuth: false })

    expect(screen.getByDisplayValue('Alice')).toBeInTheDocument()
    expect(screen.getByDisplayValue('alice@example.com')).toBeInTheDocument()
  })

  it('updates the profile with the changed fields', async () => {
    let putBody: unknown = null
    server.use(
      http.put('*/auth/me/profile', async ({ request }) => {
        putBody = await request.json()
        return HttpResponse.json({ id: 'u1', display_name: 'Alice B' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<AccountSettingsTab />, { withAuth: false })

    const displayName = screen.getByDisplayValue('Alice')
    await user.clear(displayName)
    await user.type(displayName, 'Alice B')
    await user.click(screen.getByRole('button', { name: 'Update Profile' }))

    expect(await screen.findByText('Profile updated')).toBeInTheDocument()
    expect(putBody).toEqual({ display_name: 'Alice B' })
  })

  it('shows a no-changes message when nothing changed', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AccountSettingsTab />, { withAuth: false })

    await user.click(screen.getByRole('button', { name: 'Update Profile' }))

    expect(await screen.findByText('No changes')).toBeInTheDocument()
  })

  it('requires a password to delete the account', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AccountSettingsTab />, { withAuth: false })

    await user.click(screen.getByRole('button', { name: 'Delete Account' }))
    const dialog = within(await screen.findByRole('alertdialog'))
    await user.click(dialog.getByRole('button', { name: 'Delete Account' }))

    expect(await screen.findByText('Password required')).toBeInTheDocument()
  })

  it('deletes the account when a password is provided', async () => {
    let deleteBody: unknown = null
    server.use(
      http.delete('*/auth/me', async ({ request }) => {
        deleteBody = await request.json()
        return HttpResponse.json({ message: 'deleted' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<AccountSettingsTab />, { withAuth: false })

    await user.click(screen.getByRole('button', { name: 'Delete Account' }))
    const dialog = within(await screen.findByRole('alertdialog'))
    await user.type(dialog.getByPlaceholderText('Password'), 'secret123')
    await user.click(dialog.getByRole('button', { name: 'Delete Account' }))

    expect(await screen.findByText('Account deleted')).toBeInTheDocument()
    expect(deleteBody).toEqual({ password: 'secret123', confirm: true })
  })
})
