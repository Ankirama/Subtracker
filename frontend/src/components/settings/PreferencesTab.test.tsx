import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { PreferencesTab } from './PreferencesTab'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

describe('PreferencesTab', () => {
  it('renders the appearance and localization sections', () => {
    renderWithProviders(<PreferencesTab />, { withAuth: false })

    expect(screen.getByText('Appearance')).toBeInTheDocument()
    expect(screen.getByText('Localization')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Save Preferences' }),
    ).toBeInTheDocument()
  })

  it('saves the preferences', async () => {
    let putBody: Record<string, unknown> | null = null
    server.use(
      http.put('*/auth/me/preferences', async ({ request }) => {
        putBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ message: 'saved' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<PreferencesTab />, { withAuth: false })

    await user.click(screen.getByRole('button', { name: 'Save Preferences' }))

    expect(await screen.findByText('Preferences updated')).toBeInTheDocument()
    expect(putBody).toMatchObject({
      theme: 'system',
      currency: 'USD',
      date_format: 'MM/DD/YYYY',
      timezone: 'UTC',
    })
  })

  it('saves the selected theme', async () => {
    let putBody: Record<string, unknown> | null = null
    server.use(
      http.put('*/auth/me/preferences', async ({ request }) => {
        putBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ message: 'saved' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<PreferencesTab />, { withAuth: false })

    await user.selectOptions(screen.getByLabelText('Theme'), 'dark')
    await user.click(screen.getByRole('button', { name: 'Save Preferences' }))

    expect(await screen.findByText('Preferences updated')).toBeInTheDocument()
    expect(putBody).toMatchObject({ theme: 'dark' })
  })
})
