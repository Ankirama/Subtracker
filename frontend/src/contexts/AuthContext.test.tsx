import { describe, it, expect, beforeEach, vi } from 'vitest'
import type { ReactNode } from 'react'
import { renderHook, act, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import i18next from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { AuthProvider, useAuth } from './AuthContext'
import { server } from '@/test/server'
import { defaultUser } from '@/test/handlers'

// Spy on navigation without needing a real Router.
const { navigateMock } = vi.hoisted(() => ({ navigateMock: vi.fn() }))
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const testI18n = i18next.createInstance()
testI18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  resources: { en: { translation: {} } },
  react: { useSuspense: false },
  interpolation: { escapeValue: false },
})

function wrapper({ children }: { children: ReactNode }) {
  return (
    <I18nextProvider i18n={testI18n}>
      <AuthProvider>{children}</AuthProvider>
    </I18nextProvider>
  )
}

function renderAuth() {
  return renderHook(() => useAuth(), { wrapper })
}

beforeEach(() => {
  localStorage.clear()
  navigateMock.mockReset()
})

describe('useAuth', () => {
  it('throws when used outside an AuthProvider', () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      'useAuth must be used within AuthProvider',
    )
  })
})

describe('AuthProvider', () => {
  it('starts unauthenticated when there is no token', async () => {
    const { result } = renderAuth()

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('restores the session when a token is present', async () => {
    localStorage.setItem('access_token', 'existing-token')
    const { result } = renderAuth()

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true))
    expect(result.current.user?.email).toBe(defaultUser.email)
  })

  it('clears tokens when the session restore fails', async () => {
    localStorage.setItem('access_token', 'bad-token')
    localStorage.setItem('refresh_token', 'bad-refresh')
    // Use 500 (not 401) so the failure is handled purely by AuthContext's catch
    // branch and does not trigger the client's 401 refresh/redirect interceptor.
    server.use(
      http.get('*/auth/me', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    )
    const { result } = renderAuth()

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('logs in, stores tokens and navigates to the dashboard', async () => {
    server.use(
      http.post('*/auth/login', () =>
        HttpResponse.json({
          access_token: 'tok-access',
          refresh_token: 'tok-refresh',
          token_type: 'bearer',
        }),
      ),
    )
    const { result } = renderAuth()
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.login({
        email: 'test@example.com',
        password: 'secret',
      })
    })

    expect(localStorage.getItem('access_token')).toBe('tok-access')
    expect(localStorage.getItem('refresh_token')).toBe('tok-refresh')
    expect(result.current.isAuthenticated).toBe(true)
    expect(navigateMock).toHaveBeenCalledWith('/dashboard')
  })

  it('does not authenticate when two-factor is required', async () => {
    server.use(
      http.post('*/auth/login', () =>
        HttpResponse.json({ requires_two_factor: true, message: '2FA required' }),
      ),
    )
    const { result } = renderAuth()
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.login({
        email: 'test@example.com',
        password: 'secret',
      })
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('logs out, clears the user and navigates to login', async () => {
    localStorage.setItem('access_token', 'existing-token')
    server.use(http.post('*/auth/logout', () => new HttpResponse(null, { status: 204 })))
    const { result } = renderAuth()
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true))

    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.user).toBeNull()
    expect(navigateMock).toHaveBeenCalledWith('/login')
  })

  it('registers without setting tokens or navigating', async () => {
    server.use(
      http.post('*/auth/register', () =>
        HttpResponse.json({ message: 'Check your email to verify your account' }),
      ),
    )
    const { result } = renderAuth()
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.register({
        email: 'new@example.com',
        password: 'secret',
      } as Parameters<typeof result.current.register>[0])
    })

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('completes login after 2FA and navigates to the dashboard', async () => {
    const { result } = renderAuth()
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.completeLogin()
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user?.email).toBe(defaultUser.email)
    expect(navigateMock).toHaveBeenCalledWith('/dashboard')
  })
})
