import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { BottomNav } from './BottomNav'
import { renderWithProviders } from '@/test/renderWithProviders'

const ITEMS: Array<[string, string]> = [
  ['Dashboard', '/dashboard'],
  ['Subscriptions', '/subscriptions'],
  ['Notifications', '/notifications'],
  ['Profile', '/settings/2fa'],
]

describe('BottomNav', () => {
  it('renders every nav item with the correct link target', () => {
    renderWithProviders(<BottomNav />, { withAuth: false, route: '/dashboard' })

    for (const [label, path] of ITEMS) {
      expect(screen.getByRole('link', { name: label })).toHaveAttribute(
        'href',
        path,
      )
    }
  })

  it('marks the current route as active', () => {
    // The active item gets a distinct (bold/coloured) style; Chakra emits that
    // via an emotion class, so compare class names rather than computed style
    // (jsdom does not resolve emotion sheets through getComputedStyle).
    renderWithProviders(<BottomNav />, { withAuth: false, route: '/subscriptions' })

    const active = screen.getByText('Subscriptions')
    const inactiveA = screen.getByText('Dashboard')
    const inactiveB = screen.getByText('Profile')

    expect(inactiveA.className).toBe(inactiveB.className)
    expect(active.className).not.toBe(inactiveA.className)
  })

  it('treats notification sub-routes as active', () => {
    renderWithProviders(<BottomNav />, {
      withAuth: false,
      route: '/notifications/abc-123',
    })

    expect(screen.getByText('Notifications').className).not.toBe(
      screen.getByText('Dashboard').className,
    )
  })
})
