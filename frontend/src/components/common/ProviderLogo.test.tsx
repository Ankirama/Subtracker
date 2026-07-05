import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { ProviderLogo } from './ProviderLogo'
import { renderWithProviders } from '@/test/renderWithProviders'

describe('ProviderLogo', () => {
  it('renders an avatar labelled with the provider name', () => {
    renderWithProviders(<ProviderLogo providerName="Netflix" />, {
      withAuth: false,
    })

    // Chakra Avatar exposes the name as an accessible image label.
    expect(screen.getByRole('img', { name: 'Netflix' })).toBeInTheDocument()
  })

  it('renders without crashing when a custom logo URL is provided', () => {
    const { container } = renderWithProviders(
      <ProviderLogo providerName="Spotify" customLogoUrl="https://cdn.test/sp.png" />,
      { withAuth: false },
    )

    expect(container.querySelector('.chakra-avatar')).not.toBeNull()
  })
})
