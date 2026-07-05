import { describe, it, expect, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import i18n from '@/i18n/config'
import { LanguageSwitcher } from './LanguageSwitcher'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'

afterEach(async () => {
  await i18n.changeLanguage('en')
})

describe('LanguageSwitcher', () => {
  it('renders both language options in the buttons variant', () => {
    renderWithProviders(<LanguageSwitcher variant="buttons" />, {
      withAuth: false,
    })

    expect(screen.getByRole('button', { name: /English/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Français/ })).toBeInTheDocument()
  })

  it('changes the language and persists the preference', async () => {
    let patchedBody: unknown = null
    server.use(
      http.patch('*/auth/me/language', async ({ request }) => {
        patchedBody = await request.json()
        return HttpResponse.json({ language: 'fr' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<LanguageSwitcher variant="buttons" />, {
      withAuth: false,
    })

    await user.click(screen.getByRole('button', { name: /Français/ }))

    await waitFor(() => expect(i18n.language).toBe('fr'))
    expect(patchedBody).toEqual({ language: 'fr' })
  })
})
