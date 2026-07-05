import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { SwipeableCard } from './SwipeableCard'
import { renderWithProviders } from '@/test/renderWithProviders'

describe('SwipeableCard', () => {
  it('renders its children', () => {
    renderWithProviders(
      <SwipeableCard>
        <div>Card content</div>
      </SwipeableCard>,
      { withAuth: false },
    )

    expect(screen.getByText('Card content')).toBeInTheDocument()
  })
})
